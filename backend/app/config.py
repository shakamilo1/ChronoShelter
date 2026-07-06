from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR.parent / ".env")
load_dotenv(ROOT_DIR / ".env")

class Settings:
    db_host: str = os.getenv("CHRONOSHELTER_DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("CHRONOSHELTER_DB_PORT", "3306"))
    db_user: str = os.getenv("CHRONOSHELTER_DB_USER", "chronoshelter")
    db_password: str = os.getenv("CHRONOSHELTER_DB_PASSWORD", "")
    db_name: str = os.getenv("CHRONOSHELTER_DB_NAME", "chronoshelter")
    app_host: str = os.getenv("CHRONOSHELTER_APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("CHRONOSHELTER_APP_PORT", "8000"))

    @property
    def mysql_kwargs(self) -> dict:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
            "charset": "utf8mb4",
            "autocommit": True,
        }

@lru_cache
def get_settings() -> Settings:
    return Settings()
