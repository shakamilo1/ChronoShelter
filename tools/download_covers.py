from __future__ import annotations

import argparse
import os
import re
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COVERS_DIR = ROOT / "covers"
LOG_FILE = ROOT / "logs" / "cover_download.log"
IMAGE_API = "https://api.bgm.tv/v0/subjects/{subject_id}/image?type=large"
NO_ICON_URL = "https://lain.bgm.tv/img/no_icon_subject.png"
MAX_BYTES = 5 * 1024 * 1024
MIN_BYTES = 1024
STOP_REQUESTED = False


@dataclass
class DownloadResult:
    ok: bool
    status: str
    error: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None


def _handle_stop(signum, frame):  # noqa: ARG001
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\n收到停止信号，当前下载完成后安全退出。", flush=True)


def db_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit(f"Unsafe database identifier: {name}")
    return name


def connect_db(database: str):
    database = db_identifier(database)
    try:
        import pymysql  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local operator env
        raise SystemExit("请先安装依赖：python -m pip install PyMySQL Pillow") from exc
    try:
        return pymysql.connect(
            host=os.getenv("CHRONOSHELTER_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("CHRONOSHELTER_DB_PORT", "3306")),
            user=os.getenv("CHRONOSHELTER_DB_USER", "chronoshelter"),
            password=os.getenv("CHRONOSHELTER_DB_PASSWORD", "change-me"),
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        raise SystemExit(f"无法连接 MariaDB 数据库 {database}: {exc}") from exc


def local_cover_path(subject_id: int) -> Path:
    return COVERS_DIR / f"{subject_id}.jpg"


def missing_subject_ids(limit: int | None = None) -> list[int]:
    public_db = db_identifier(os.getenv("CHRONOSHELTER_PUBLIC_DB_NAME", "chrono_bangumi"))
    library_db = db_identifier(os.getenv("CHRONOSHELTER_LIBRARY_DB_NAME", "chrono_library"))
    sql = f"""
        SELECT s.id
        FROM `{public_db}`.`subjects` s
        LEFT JOIN `{library_db}`.`cover_cache` cc ON cc.subject_id = s.id AND cc.status = 'cached'
        WHERE s.type = 2 AND cc.subject_id IS NULL
        ORDER BY s.id
    """
    if limit is not None:
        sql += " LIMIT %s"
    with connect_db(public_db) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,) if limit is not None else None)
            rows = cur.fetchall()
    return [int(row["id"]) for row in rows if not local_cover_path(int(row["id"])).exists()]


def detect_image(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local operator env
        raise SystemExit("请先安装 Pillow 用于验证图片完整性：python -m pip install Pillow") from exc
    try:
        with Image.open(path) as image:
            size = image.size
            image.verify()
            return size
    except Exception:  # pragma: no cover - depends on corrupt image bytes
        return None


def log_failure(subject_id: int, error: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\tsubject_id={subject_id}\terror={error}\n")


def update_cache(subject_id: int, result: DownloadResult) -> None:
    library_db = db_identifier(os.getenv("CHRONOSHELTER_LIBRARY_DB_NAME", "chrono_library"))
    with connect_db(library_db) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cover_cache (subject_id, status, local_path, error, content_type, file_size, width, height)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), local_path=VALUES(local_path), error=VALUES(error),
                    content_type=VALUES(content_type), file_size=VALUES(file_size), width=VALUES(width), height=VALUES(height)
                """,
                (
                    subject_id,
                    result.status,
                    f"covers/{subject_id}.jpg" if result.ok else None,
                    result.error,
                    result.content_type,
                    result.file_size,
                    result.width,
                    result.height,
                ),
            )


def download_cover(subject_id: int, timeout: int = 10) -> DownloadResult:
    target = local_cover_path(subject_id)
    if target.exists() and target.stat().st_size > 0:
        return DownloadResult(ok=True, status="cached", file_size=target.stat().st_size)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    req = Request(IMAGE_API.format(subject_id=subject_id), headers={"User-Agent": "ChronoShelter/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - fixed Bangumi image API
            if response.geturl() == NO_ICON_URL:
                return DownloadResult(ok=False, status="invalid", error="Bangumi no-icon placeholder")
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_BYTES + 1)
            status = getattr(response, "status", 200)
    except (OSError, URLError, TimeoutError) as exc:
        return DownloadResult(ok=False, status="failed", error=str(exc))
    if status != 200:
        return DownloadResult(ok=False, status="failed", error=f"HTTP {status}", content_type=content_type)
    if not content_type.lower().startswith("image/"):
        return DownloadResult(ok=False, status="failed", error="unexpected content type", content_type=content_type)
    if len(data) < MIN_BYTES or len(data) > MAX_BYTES:
        return DownloadResult(ok=False, status="failed", error="unexpected file size", content_type=content_type, file_size=len(data))
    with tempfile.NamedTemporaryFile(delete=False, dir=COVERS_DIR, suffix=".tmp") as fh:
        tmp_path = Path(fh.name)
        fh.write(data)
    try:
        size = detect_image(tmp_path)
        if not size:
            return DownloadResult(ok=False, status="failed", error="invalid image", content_type=content_type, file_size=len(data))
        tmp_path.replace(target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return DownloadResult(ok=True, status="cached", content_type=content_type, file_size=len(data), width=size[0], height=size[1])


def run_missing(limit: int | None, delay: float) -> None:
    signal.signal(signal.SIGINT, _handle_stop)
    print("开始下载封面")
    ids = missing_subject_ids(limit)
    total = len(ids)
    print(f"发现缺失:\n{total}")
    for index, subject_id in enumerate(ids, start=1):
        if STOP_REQUESTED:
            break
        print(f"\n[{index}/{total}]\nsubject_id:\n{subject_id}")
        result = download_cover(subject_id)
        update_cache(subject_id, result)
        if result.ok:
            print("状态:\n成功")
        else:
            print(f"状态:\n失败：{result.error}")
            log_failure(subject_id, result.error or "unknown error")
        if index < total and not STOP_REQUESTED:
            time.sleep(delay)
    print("已安全退出。" if STOP_REQUESTED else "封面下载完成。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download missing ChronoShelter covers into covers/{subject_id}.jpg.")
    parser.add_argument("--missing", action="store_true", default=True, help="Download missing anime covers (default).")
    parser.add_argument("--limit", type=int, help="Maximum number of covers to process.")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between downloads. Default: 3.")
    args = parser.parse_args(argv)
    run_missing(args.limit, args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
