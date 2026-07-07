from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.database import get_connection, library_database_name, public_database_name


def inspect_table(database: str, table_name: str):
    with get_connection(database) as conn, conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (table_name,))
        exists = bool(cur.fetchone())
        if not exists:
            print(f"[{database}.{table_name}] missing")
            return
        cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        columns = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) AS row_count FROM `{table_name}`")
        row_count = cur.fetchone()["row_count"]
    print(f"[{database}.{table_name}] rows={row_count}")
    for col in columns:
        nullable = "NULL" if col.get("Null") == "YES" else "NOT NULL"
        print(f"- {col['Field']} {col['Type']} {nullable} default={col.get('Default')}")


def main():
    print("ChronoShelter schema inspection (read-only)")
    public_db = public_database_name()
    library_db = library_database_name()
    for table in ("subjects", "episodes", "persons", "characters", "subject_persons", "subject_characters", "subject_relations", "person_characters", "person_relations"):
        inspect_table(public_db, table)
    inspect_table(library_db, "collections")


if __name__ == "__main__":
    main()
