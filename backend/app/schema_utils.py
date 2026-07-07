from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=64)
def get_table_columns(table_name: str, database: str | None = None) -> set[str]:
    from .database import get_connection
    with get_connection(database) as conn, conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (table_name,))
        if not cur.fetchone():
            return set()
        cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        return {row["Field"] for row in cur.fetchall()}


def table_exists(table_name: str, database: str | None = None) -> bool:
    return bool(get_table_columns(table_name, database))
