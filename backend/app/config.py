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
    public_db_name: str = os.getenv("CHRONOSHELTER_PUBLIC_DB_NAME", os.getenv("CHRONOSHELTER_DB_NAME", "chrono_bangumi"))
    library_db_name: str = os.getenv("CHRONOSHELTER_LIBRARY_DB_NAME", "chrono_library")
    app_host: str = os.getenv("CHRONOSHELTER_APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("CHRONOSHELTER_APP_PORT", "8700"))

    def mysql_kwargs(self, database: str | None = None) -> dict:
        kwargs = {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "charset": "utf8mb4",
            "autocommit": True,
        }
        if database != "__server__":
            kwargs["database"] = database or self.public_db_name
        return kwargs

@lru_cache
def get_settings() -> Settings:
    return Settings()
