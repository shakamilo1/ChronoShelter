from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.database import get_connection

ARCHIVE_TABLES = [
    "subject",
    "episode",
    "person",
    "character",
    "subject_person",
    "subject_character",
    "subject_relation",
    "person_character",
    "person_relation",
]


def download_release(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
    with urlopen(req, timeout=120) as response:  # noqa: S310 - operator-provided release URL
        dest.write_bytes(response.read())
    return dest


def extract_zip(zip_path: Path, out_dir: Path) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    return out_dir


def create_temp_database(name: str):
    settings = get_settings()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"created_temp_database={name}")


def validate_temp_database(name: str) -> bool:
    settings = get_settings()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
        if not cur.fetchone():
            print(f"validation_failed=temp database {name} missing")
            return False
        for table in ARCHIVE_TABLES:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                (name, table),
            )
            if cur.fetchone()["cnt"] == 0:
                print(f"validation_failed=missing table {name}.{table}")
                return False
    print("validation_ok=true")
    return True


def plan_swap(temp_db: str):
    settings = get_settings()
    print("Archive swap is intentionally not automatic in MVP.")
    print(f"validated_temp_db={temp_db}")
    print(f"production_db={settings.db_name}")
    print("Review the temp database, take a backup, then swap Archive public tables during a maintenance window.")
    print("my_collection is not part of ARCHIVE_TABLES and must never be swapped or rebuilt by Archive updates.")


def main():
    parser = argparse.ArgumentParser(description="Download and stage a Bangumi Archive release without overwriting production tables.")
    parser.add_argument("--url", help="Bangumi Archive release zip URL")
    parser.add_argument("--zip", type=Path, default=ROOT / "data" / "archive" / "release.zip")
    parser.add_argument("--extract-dir", type=Path, default=ROOT / "data" / "archive" / "extracted")
    parser.add_argument("--temp-db", default="chronoshelter_archive_tmp")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--create-temp-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--plan-swap", action="store_true")
    args = parser.parse_args()

    if args.download:
        if not args.url:
            raise SystemExit("--url is required with --download")
        download_release(args.url, args.zip)
        print(f"downloaded={args.zip}")
    if args.extract:
        extract_zip(args.zip, args.extract_dir)
        print(f"extracted={args.extract_dir}")
    if args.create_temp_db:
        create_temp_database(args.temp_db)
    if args.validate:
        if not validate_temp_database(args.temp_db):
            raise SystemExit(1)
    if args.plan_swap:
        plan_swap(args.temp_db)


if __name__ == "__main__":
    main()
