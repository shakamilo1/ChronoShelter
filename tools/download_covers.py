#!/usr/bin/env python3
"""Offline Bangumi anime cover synchronizer for ChronoShelter.

Runs on a maintenance machine (for example Windows with VPN) and writes covers,
SQLite state, and JSONL mapping files that the NAS/PHP deployment can import.
It never connects to production MariaDB.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sqlite3
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://api.bgm.tv/v0/subjects"
SUBJECT_TYPE = 2
PAGE_LIMIT = 50
USER_AGENT = "shakamilo1/ChronoShelter-cover-sync/1.0 (https://github.com/shakamilo1/ChronoShelter)"
ALLOWED_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
FILENAME_RE_TEMPLATE = r"^{sid}_[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$"


class CoverSyncError(RuntimeError):
    pass


class RemoteMissingCover(CoverSyncError):
    pass


@dataclass
class DownloadMeta:
    tmp_path: Path
    final_url: str
    content_type: str
    extension: str
    file_size: int
    sha256: str
    etag: str | None = None
    last_modified: str | None = None


def covers_dir() -> Path:
    return Path(os.environ.get("CHRONOSHELTER_COVERS_DIR", PROJECT_ROOT / "covers"))


def state_dir() -> Path:
    return Path(os.environ.get("CHRONOSHELTER_COVER_SYNC_STATE_DIR", PROJECT_ROOT / "var" / "cover-sync"))


def tmp_dir() -> Path:
    return state_dir() / "tmp"


def reports_dir() -> Path:
    return state_dir() / "reports"


def sqlite_path() -> Path:
    return state_dir() / "covers.sqlite"


def ensure_dirs() -> None:
    for path in (state_dir(), tmp_dir(), reports_dir(), covers_dir()):
        path.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    ensure_dirs()
    con = sqlite3.connect(sqlite_path())
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cover_manifest (
            subject_id INTEGER PRIMARY KEY,
            subject_type INTEGER NOT NULL DEFAULT 2,
            downloaded_url TEXT,
            observed_url TEXT,
            remote_filename TEXT,
            relative_path TEXT,
            mime_type TEXT,
            file_extension TEXT,
            file_size INTEGER,
            sha256 TEXT,
            etag TEXT,
            last_modified TEXT,
            artifact_status TEXT,
            deploy_status TEXT,
            last_check_result TEXT,
            last_error TEXT,
            checked_at TEXT,
            last_success_at TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            run_type TEXT PRIMARY KEY,
            next_offset INTEGER NOT NULL DEFAULT 0,
            total INTEGER,
            updated_at TEXT NOT NULL
        )
        """
    )
    return con


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def partition_prefix(subject_id: int) -> PurePosixPath:
    return PurePosixPath("subjects") / f"{subject_id // 1_000_000:03d}" / f"{(subject_id % 1_000_000) // 1_000:03d}"


def safe_remote_filename(subject_id: int, url: str, detected_ext: str) -> str:
    path = urllib.parse.urlparse(url).path
    basename = urllib.parse.unquote(PurePosixPath(path).name)
    if any(ch in basename for ch in ("/", "\\")) or ".." in basename or any(ord(ch) < 32 or ord(ch) == 127 for ch in basename):
        basename = ""
    match = re.match(FILENAME_RE_TEMPLATE.format(sid=re.escape(str(subject_id))), basename, re.I)
    if match:
        ext = match.group(1).lower().replace("jpeg", "jpg")
        if ext != detected_ext:
            raise CoverSyncError("remote filename extension does not match detected image type")
        return basename
    return f"{subject_id}_{sha256(url.encode('utf-8')).hexdigest()[:12]}.{detected_ext}"


def cover_relative_path(subject_id: int, filename: str) -> PurePosixPath:
    if not re.match(rf"^{subject_id}_[A-Za-z0-9_-]+(?:--[a-f0-9]{{12}}|--[a-f0-9]{{64}})?\.(jpg|jpeg|png|webp)$", filename, re.I):
        raise CoverSyncError("invalid cover filename")
    return partition_prefix(subject_id) / filename


def cover_absolute_path(relative: str | PurePosixPath) -> Path:
    rel = PurePosixPath(str(relative).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise CoverSyncError("unsafe cover path")
    return covers_dir() / Path(*rel.parts)


def is_no_icon(url: str) -> bool:
    return PurePosixPath(urllib.parse.urlparse(url).path).name == "no_icon_subject.png"


def normalize_api_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.bgm.tv" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise CoverSyncError("refusing to send Bangumi API request outside https://api.bgm.tv:443")
    return parsed


def api_headers(url: str) -> dict[str, str]:
    normalize_api_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    token = os.environ.get("BANGUMI_ACCESS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def image_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "image/webp,image/png,image/jpeg,*/*;q=0.8"}
    for key, value in (extra or {}).items():
        if key.lower() == "authorization":
            continue
        headers[key] = value
    return headers


def proxy_handler(proxy: str | None) -> urllib.request.ProxyHandler:
    if proxy:
        return urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    return urllib.request.ProxyHandler()


def opener(proxy: str | None) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(proxy_handler(proxy), urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def request_once(url: str, headers: dict[str, str], proxy: str | None, timeout: float) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with opener(proxy).open(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read()
    except urllib.error.URLError as exc:
        raise CoverSyncError(f"network error: {exc.reason}") from exc


def should_retry(status: int) -> bool:
    return status in {429, 500, 502, 503, 504}


def sleep_for_retry(headers: dict[str, str], attempt: int) -> None:
    retry_after = headers.get("retry-after")
    delay = min(30.0, float(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt) + random.random())
    time.sleep(delay)


def http_get(url: str, headers: dict[str, str], proxy: str | None, timeout: float, retries: int = 3) -> tuple[int, dict[str, str], bytes]:
    for attempt in range(1, retries + 1):
        status, response_headers, body = request_once(url, headers, proxy, timeout)
        if not should_retry(status) or attempt == retries:
            return status, response_headers, body
        sleep_for_retry(response_headers, attempt)
    raise AssertionError("unreachable")


def fetch_subject_page(offset: int, proxy: str | None, timeout: float = 30) -> dict[str, Any]:
    params = urllib.parse.urlencode({"type": SUBJECT_TYPE, "limit": PAGE_LIMIT, "offset": offset})
    url = f"{API_URL}?{params}"
    status, headers, body = http_get(url, api_headers(url), proxy, timeout)
    if 300 <= status < 400:
        raise CoverSyncError("Bangumi API redirect refused")
    if status != 200:
        raise CoverSyncError(f"Bangumi API failed: HTTP {status}")
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise CoverSyncError(f"Bangumi API JSON parse failed: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(data.get(k), int) and data[k] >= 0 for k in ("total", "limit", "offset")) or not isinstance(data.get("data"), list):
        raise CoverSyncError("Bangumi API Paged_Subject shape is invalid")
    if data["limit"] > PAGE_LIMIT or data["offset"] != offset:
        raise CoverSyncError("Bangumi API pagination fields do not match request")
    if offset < data["total"] and not data["data"]:
        raise CoverSyncError("Bangumi API returned empty data before total was reached")
    return data


def follow_image_redirects(url: str, proxy: str | None, timeout: float = 45, max_redirects: int = 5) -> tuple[int, dict[str, str], bytes, str]:
    current = url
    for _ in range(max_redirects + 1):
        parsed = urllib.parse.urlparse(current)
        if parsed.scheme != "https" or not parsed.hostname:
            raise CoverSyncError("invalid or unsafe image URL/redirect")
        if is_no_icon(current):
            raise RemoteMissingCover("Bangumi no-icon placeholder rejected")
        status, headers, body = http_get(current, image_headers(), proxy, timeout)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location:
                raise CoverSyncError("image redirect missing Location")
            current = urllib.parse.urljoin(current, location)
            continue
        if is_no_icon(current):
            raise RemoteMissingCover("Bangumi no-icon placeholder rejected")
        return status, headers, body, current
    raise CoverSyncError("too many image redirects")


def image_type(data: bytes, content_type: str) -> tuple[str, str] | None:
    ctype = content_type.split(";", 1)[0].strip().lower()
    if data.startswith(b"\xff\xd8\xff") and ctype in {"image/jpeg", "image/jpg"}:
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n") and ctype == "image/png":
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and ctype == "image/webp":
        return "image/webp", "webp"
    return None


def validate_png(data: bytes) -> bool:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        chunk_type = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            return False
        expected = int.from_bytes(data[end:end + 4], "big")
        if zlib.crc32(chunk_type + data[start:end]) & 0xFFFFFFFF != expected:
            return False
        offset = end + 4
        if chunk_type == b"IEND":
            return offset == len(data)
    return False


def validate_image_bytes(data: bytes, content_type: str) -> tuple[str, str]:
    if len(data) < 32 or len(data) > 20 * 1024 * 1024 or data.lstrip()[:1] in {b"<", b"{", b"["}:
        raise CoverSyncError("downloaded content is not a valid image")
    detected = image_type(data, content_type)
    if detected is None:
        raise CoverSyncError("unsupported or mismatched image type")
    mime, ext = detected
    if ext == "jpg" and not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise CoverSyncError("JPEG structure is incomplete")
    if ext == "png" and not validate_png(data):
        raise CoverSyncError("PNG structure is incomplete or CRC is invalid")
    if ext == "webp" and (len(data) < 12 or int.from_bytes(data[4:8], "little") + 8 != len(data)):
        raise CoverSyncError("WebP RIFF length is invalid")
    return mime, ext


def download_image(subject_id: int, url: str, proxy: str | None) -> DownloadMeta:
    ensure_dirs()
    fd, name = tempfile.mkstemp(prefix=f"{subject_id}-", suffix=".part", dir=tmp_dir())
    os.close(fd)
    tmp = Path(name)
    try:
        status, headers, body, final_url = follow_image_redirects(url, proxy)
        if status != 200:
            raise CoverSyncError(f"image download failed: HTTP {status}")
        mime, ext = validate_image_bytes(body, headers.get("content-type", ""))
        tmp.write_bytes(body)
        digest = sha256(body).hexdigest()
        return DownloadMeta(tmp, final_url, mime, ext, len(body), digest, headers.get("etag"), headers.get("last-modified"))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def place_cover(subject_id: int, source_url: str, meta: DownloadMeta) -> tuple[str, str]:
    remote = safe_remote_filename(subject_id, source_url, meta.extension)
    rel = cover_relative_path(subject_id, remote)
    target = cover_absolute_path(rel)
    if target.exists():
        existing_sha = sha256(target.read_bytes()).hexdigest()
        if existing_sha == meta.sha256:
            meta.tmp_path.unlink(missing_ok=True)
            return remote, rel.as_posix()
        stem = Path(remote).stem
        ext = Path(remote).suffix.lstrip(".").lower().replace("jpeg", "jpg")
        for size in (12, 64):
            rel = cover_relative_path(subject_id, f"{stem}--{meta.sha256[:size]}.{ext}")
            target = cover_absolute_path(rel)
            if not target.exists():
                break
            if sha256(target.read_bytes()).hexdigest() == meta.sha256:
                meta.tmp_path.unlink(missing_ok=True)
                return remote, rel.as_posix()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(meta.tmp_path, "rb") as src, open(target, "xb") as dst:
        shutil.copyfileobj(src, dst)
    meta.tmp_path.unlink(missing_ok=True)
    return remote, rel.as_posix()


def subject_url(item: dict[str, Any]) -> str | None:
    images = item.get("images")
    if not isinstance(images, dict):
        return None
    url = images.get("large")
    if not isinstance(url, str) or not url.strip() or is_no_icon(url):
        return None
    return url


def save_missing(con: sqlite3.Connection, subject_id: int, observed_url: str | None, result: str, error: str | None = None) -> None:
    old = con.execute("SELECT relative_path FROM cover_manifest WHERE subject_id=?", (subject_id,)).fetchone()
    artifact = "available" if old and old["relative_path"] else "missing"
    con.execute(
        """INSERT INTO cover_manifest (subject_id, subject_type, observed_url, artifact_status, deploy_status, last_check_result, last_error, checked_at)
        VALUES (?, 2, ?, ?, 'pending_deploy', ?, ?, ?)
        ON CONFLICT(subject_id) DO UPDATE SET observed_url=excluded.observed_url, artifact_status=?, last_check_result=excluded.last_check_result, last_error=excluded.last_error, checked_at=excluded.checked_at""",
        (subject_id, observed_url, artifact, result, error, now(), artifact),
    )
    con.commit()


def sync(args: argparse.Namespace) -> int:
    con = connect_db()
    run_type = "sync"
    offset = 0
    row = con.execute("SELECT next_offset FROM sync_runs WHERE run_type=?", (run_type,)).fetchone()
    if args.resume and row:
        offset = int(row["next_offset"])
    processed = 0
    pages = 0
    while True:
        if args.max_pages is not None and pages >= args.max_pages:
            break
        page = fetch_subject_page(offset, args.proxy)
        total = int(page["total"])
        data = page["data"]
        if offset >= total:
            break
        for item in data:
            if args.max_items is not None and processed >= args.max_items:
                con.execute("INSERT INTO sync_runs (run_type,next_offset,total,updated_at) VALUES (?,?,?,?) ON CONFLICT(run_type) DO UPDATE SET next_offset=excluded.next_offset,total=excluded.total,updated_at=excluded.updated_at", (run_type, offset, total, now()))
                con.commit()
                return 0
            offset += 1
            if not isinstance(item, dict) or int(item.get("type", 0)) != SUBJECT_TYPE:
                continue
            subject_id = int(item.get("id", 0))
            if subject_id <= 0:
                raise CoverSyncError("invalid subject id")
            url = subject_url(item)
            if not url:
                save_missing(con, subject_id, None, "remote_missing")
                processed += 1
                continue
            old = con.execute("SELECT downloaded_url, relative_path, sha256 FROM cover_manifest WHERE subject_id=?", (subject_id,)).fetchone()
            if old and old["downloaded_url"] == url and old["relative_path"] and cover_absolute_path(old["relative_path"]).is_file():
                con.execute("UPDATE cover_manifest SET observed_url=?, last_check_result='unchanged', checked_at=? WHERE subject_id=?", (url, now(), subject_id))
                con.commit()
                processed += 1
                continue
            try:
                meta = download_image(subject_id, url, args.proxy)
                remote, rel = place_cover(subject_id, url, meta)
                con.execute(
                    """INSERT INTO cover_manifest (subject_id, subject_type, downloaded_url, observed_url, remote_filename, relative_path, mime_type, file_extension, file_size, sha256, etag, last_modified, artifact_status, deploy_status, last_check_result, last_error, checked_at, last_success_at)
                    VALUES (?,2,?,?,?,?,?,?,?,?,?,?, 'available','pending_deploy','updated',NULL,?,?)
                    ON CONFLICT(subject_id) DO UPDATE SET downloaded_url=excluded.downloaded_url, observed_url=excluded.observed_url, remote_filename=excluded.remote_filename, relative_path=excluded.relative_path, mime_type=excluded.mime_type, file_extension=excluded.file_extension, file_size=excluded.file_size, sha256=excluded.sha256, etag=excluded.etag, last_modified=excluded.last_modified, artifact_status='available', deploy_status='pending_deploy', last_check_result='updated', last_error=NULL, checked_at=excluded.checked_at, last_success_at=excluded.last_success_at""",
                    (subject_id, url, url, remote, rel, meta.content_type, meta.extension, meta.file_size, meta.sha256, meta.etag, meta.last_modified, now(), now()),
                )
                con.commit()
            except RemoteMissingCover:
                save_missing(con, subject_id, url, "remote_missing")
            except Exception as exc:
                save_missing(con, subject_id, url, "http_failed", str(exc))
            processed += 1
            if args.download_delay:
                time.sleep(args.download_delay)
        pages += 1
        con.execute("INSERT INTO sync_runs (run_type,next_offset,total,updated_at) VALUES (?,?,?,?) ON CONFLICT(run_type) DO UPDATE SET next_offset=excluded.next_offset,total=excluded.total,updated_at=excluded.updated_at", (run_type, offset, total, now()))
        con.commit()
        if offset >= total:
            break
        if args.api_delay:
            time.sleep(args.api_delay)
    print(json.dumps({"processed": processed, "next_offset": offset}, ensure_ascii=False))
    return 0


def verify_files(args: argparse.Namespace) -> int:
    con = connect_db()
    failed = 0
    for row in con.execute("SELECT * FROM cover_manifest WHERE relative_path IS NOT NULL"):
        path = cover_absolute_path(row["relative_path"])
        try:
            data = path.read_bytes()
            mime, ext = validate_image_bytes(data, row["mime_type"] or "")
            if ext != row["file_extension"] or len(data) != row["file_size"] or sha256(data).hexdigest() != row["sha256"]:
                raise CoverSyncError("metadata mismatch")
        except Exception as exc:
            failed += 1
            con.execute("UPDATE cover_manifest SET artifact_status='invalid', last_check_result='local_invalid', last_error=?, checked_at=? WHERE subject_id=?", (str(exc), now(), row["subject_id"]))
    con.commit()
    print(json.dumps({"failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


def export_mapping(args: argparse.Namespace) -> int:
    con = connect_db()
    out = Path(args.file or reports_dir() / f"cover-mapping-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in con.execute("SELECT * FROM cover_manifest ORDER BY subject_id"):
            if row["relative_path"] and row["sha256"]:
                item = {"subject_id": row["subject_id"], "status": "cached", "remote_filename": row["remote_filename"], "source_url": row["downloaded_url"], "local_path": row["relative_path"], "content_type": row["mime_type"], "file_size": row["file_size"], "sha256": row["sha256"], "updated_at": row["last_success_at"] or row["checked_at"]}
            elif row["artifact_status"] == "missing" and row["last_check_result"] == "remote_missing":
                item = {"subject_id": row["subject_id"], "status": "no_cover", "remote_filename": None, "source_url": None, "local_path": None, "content_type": None, "file_size": None, "sha256": None, "updated_at": row["checked_at"]}
            else:
                continue
            fh.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    print(json.dumps({"file": str(out), "records": count}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Bangumi anime cover synchronizer (type=2 only).")
    sub = parser.add_subparsers(dest="command", required=True)
    sync_p = sub.add_parser("sync")
    sync_p.add_argument("--resume", action="store_true")
    sync_p.add_argument("--max-pages", type=int)
    sync_p.add_argument("--max-items", type=int)
    sync_p.add_argument("--api-delay", type=float, default=1.0)
    sync_p.add_argument("--download-delay", type=float, default=1.0)
    sync_p.add_argument("--verbose", action="store_true")
    sync_p.add_argument("--proxy")
    verify_p = sub.add_parser("verify-files")
    verify_p.add_argument("--verbose", action="store_true")
    export_p = sub.add_parser("export-mapping")
    export_p.add_argument("--file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sync":
            return sync(args)
        if args.command == "verify-files":
            return verify_files(args)
        if args.command == "export-mapping":
            return export_mapping(args)
        raise CoverSyncError("unknown command")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
