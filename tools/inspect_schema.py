from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.php_config_reader import database_config


def connect_database(kind: str):
    try:
        import pymysql  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on operator environment
        raise SystemExit("请先安装 PyMySQL：python -m pip install PyMySQL") from exc
    config = database_config(kind)
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset=config.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def table_columns(kind: str, table: str):
    config = database_config(kind)
    with connect_database(kind) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ORDINAL_POSITION",
            (config["database"], table),
        )
        return cur.fetchall()


def table_count(kind: str, table: str):
    with connect_database(kind) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS count FROM `{table}`")
        return cur.fetchone()["count"]


def main():
    print("ChronoShelter schema inspection (read-only)")
    for kind, tables in {
        "public": ["subjects", "episodes", "persons", "characters", "subject_persons", "subject_characters", "subject_relations"],
        "library": ["collections"],
    }.items():
        database = database_config(kind)["database"]
        print(f"\n[{database}]")
        for table in tables:
            try:
                cols = table_columns(kind, table)
                count = table_count(kind, table)
                print(f"{table}: rows={count} columns={', '.join(col['COLUMN_NAME'] for col in cols)}")
            except Exception as exc:  # noqa: BLE001 - inspection should continue across missing tables
                print(f"{table}: ERROR {exc}")


if __name__ == "__main__":
    main()
