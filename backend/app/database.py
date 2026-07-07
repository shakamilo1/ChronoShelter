from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor

from .config import get_settings

@contextmanager
def get_connection(database: str | None = None):
    conn = pymysql.connect(cursorclass=DictCursor, **get_settings().mysql_kwargs(database))
    try:
        yield conn
    finally:
        conn.close()


def public_database_name() -> str:
    return get_settings().public_db_name


def library_database_name() -> str:
    return get_settings().library_db_name
