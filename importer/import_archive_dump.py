from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def get_public_db_config() -> dict:
    from tools.php_config_reader import database_config

    return database_config("public")


def connect_public_database():
    try:
        import pymysql  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on operator environment
        raise SystemExit("请先安装 PyMySQL：python -m pip install PyMySQL") from exc
    config = get_public_db_config()
    try:
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
    except pymysql.MySQLError as exc:
        raise SystemExit(f"无法连接 MariaDB 数据库 {config['database']}: {exc}") from exc


def get_table_columns(table: str) -> set[str]:
    config = get_public_db_config()
    with connect_public_database() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                (config["database"], table),
            )
            return {row["COLUMN_NAME"] for row in cur.fetchall()}


ARCHIVE_FILES = {
    "subjects": "subject.jsonlines",
    "episodes": "episode.jsonlines",
    "persons": "person.jsonlines",
    "characters": "character.jsonlines",
    "subject_persons": "subject-persons.jsonlines",
    "subject_characters": "subject-characters.jsonlines",
    "subject_relations": "subject-relations.jsonlines",
    "person_characters": "person-characters.jsonlines",
    "person_relations": "person-relations.jsonlines",
}


def _json(value):
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value


def normalize_row(item: dict) -> dict:
    return {key: _json(value) for key, value in item.items()}


def build_upsert_sql(table: str, row: dict, columns: set[str]) -> tuple[str, dict] | None:
    writable = [key for key in row if key in columns]
    if not writable:
        return None
    quoted = ", ".join(f"`{col}`" for col in writable)
    values = ", ".join(f"%({col})s" for col in writable)
    updates = ", ".join(f"`{col}`=VALUES(`{col}`)" for col in writable if col != "id")
    if updates:
        sql = f"INSERT INTO `{table}` ({quoted}) VALUES ({values}) ON DUPLICATE KEY UPDATE {updates}"
    else:
        sql = f"INSERT IGNORE INTO `{table}` ({quoted}) VALUES ({values})"
    return sql, {key: row[key] for key in writable}


def import_jsonlines_file(path: Path, table: str, limit: int | None = None, dry_run: bool = False) -> tuple[int, int]:
    columns = get_table_columns(table) if not dry_run else set()
    imported = skipped = 0
    with path.open("r", encoding="utf-8") as fh:
        iterator = tqdm(fh, unit="row", desc=table) if tqdm else fh
        conn_ctx = connect_public_database() if not dry_run else _null_context()
        with conn_ctx as conn:
            for line in iterator:
                if limit is not None and imported >= limit:
                    break
                if not line.strip():
                    continue
                row = normalize_row(json.loads(line))
                if dry_run:
                    imported += 1
                    continue
                built = build_upsert_sql(table, row, columns)
                if not built:
                    skipped += 1
                    continue
                sql, params = built
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                imported += 1
    return imported, skipped


class _null_context:
    def __enter__(self):
        return None
    def __exit__(self, exc_type, exc, tb):
        return False


def import_dump(directory: Path, table: str | None = None, limit: int | None = None, dry_run: bool = False):
    targets = {table: ARCHIVE_FILES[table]} if table else ARCHIVE_FILES
    totals = {}
    for table_name, filename in targets.items():
        path = directory / filename
        if not path.exists():
            print(f"missing={path}", file=sys.stderr)
            continue
        totals[table_name] = import_jsonlines_file(path, table_name, limit=limit, dry_run=dry_run)
    for table_name, (imported, skipped) in totals.items():
        print(f"{table_name}: imported={imported} skipped={skipped}")
    return totals


def main():
    parser = argparse.ArgumentParser(description="Import Bangumi Archive jsonlines dump into chrono_bangumi tables.")
    parser.add_argument("--dir", type=Path, required=True, help="Archive dump directory containing *.jsonlines files.")
    parser.add_argument("--table", choices=sorted(ARCHIVE_FILES))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import_dump(args.dir, args.table, args.limit, args.dry_run)


if __name__ == "__main__":
    main()
