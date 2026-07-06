from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor

from .config import get_settings

@contextmanager
def get_connection():
    conn = pymysql.connect(cursorclass=DictCursor, **get_settings().mysql_kwargs)
    try:
        yield conn
    finally:
        conn.close()
