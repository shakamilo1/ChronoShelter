from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.database import get_connection


def inspect_table(table_name: str):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (table_name,))
        exists = bool(cur.fetchone())
        if not exists:
            print(f"[{table_name}] missing")
            return
        cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        columns = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) AS row_count FROM `{table_name}`")
        row_count = cur.fetchone()["row_count"]
    print(f"[{table_name}] rows={row_count}")
    for col in columns:
        nullable = "NULL" if col.get("Null") == "YES" else "NOT NULL"
        print(f"- {col['Field']} {col['Type']} {nullable} default={col.get('Default')}")


def main():
    print("ChronoShelter schema inspection (read-only)")
    inspect_table("bangumi_anime")
    inspect_table("my_collection")


if __name__ == "__main__":
    main()
