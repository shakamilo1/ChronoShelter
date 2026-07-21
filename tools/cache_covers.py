from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.download_covers import download_cover, local_cover_path, update_cache
from tools.php_config_reader import database_config


def connect_db(kind: str):
    try:
        import pymysql  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on operator environment
        raise SystemExit("请先安装依赖：python -m pip install PyMySQL Pillow") from exc
    config = database_config(kind)
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset=config.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def cover_subject_ids(all_items=False, missing=False, anime_id=None, limit=None, retry_failed=False):
    if anime_id is not None:
        return [anime_id]
    public_db = database_config("public")["database"]
    library_db = database_config("library")["database"]
    if retry_failed:
        sql = f"SELECT subject_id AS id FROM `{library_db}`.`cover_cache` WHERE status = 'failed' ORDER BY updated_at"
    elif missing and not all_items:
        sql = f"""
            SELECT s.id
            FROM `{public_db}`.`subjects` s
            LEFT JOIN `{library_db}`.`cover_cache` cc ON cc.subject_id = s.id AND cc.status = 'cached'
            WHERE s.type = 2 AND cc.subject_id IS NULL
            ORDER BY s.id
        """
    else:
        sql = f"SELECT id FROM `{public_db}`.`subjects` WHERE type = 2 ORDER BY id"
    if limit is not None:
        sql += " LIMIT %s"
    with connect_db("public") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,) if limit is not None else None)
            return [int(row["id"]) for row in cur.fetchall()]


def cache_covers(all_items=False, missing=False, anime_id=None, limit=None, retry_failed=False):
    ids = cover_subject_ids(all_items, missing, anime_id, limit, retry_failed)
    ok = failed = skipped = 0
    for subject_id in ids:
        if local_cover_path(subject_id).exists() and not all_items and not retry_failed:
            skipped += 1
            continue
        result = download_cover(subject_id)
        update_cache(subject_id, result)
        if result.ok:
            ok += 1
        else:
            failed += 1
    print(f"cached={ok} skipped={skipped} failed={failed}")
    return ok, skipped, failed


def main():
    parser = argparse.ArgumentParser(description="Cache ChronoShelter cover images without blocking the website.")
    parser.add_argument("--all", action="store_true", help="Process all subjects, even if local files exist.")
    parser.add_argument("--missing", action="store_true", help="Process subjects missing local cover files.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry subjects recorded as failed in chrono_library.cover_cache.")
    parser.add_argument("--id", type=int, dest="anime_id")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cache_covers(args.all, args.missing, args.anime_id, args.limit, args.retry_failed)


if __name__ == "__main__":
    main()
