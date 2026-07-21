from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.php"
EXAMPLE_CONFIG_PATH = ROOT / "config" / "config-example.php"


def read_php_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read shared PHP config without duplicating DB secrets.

    Production deployments should copy config/config-example.php to
    config/config.php. Tests and fresh clones can read the example file.
    """
    if not config_path.exists():
        if config_path == CONFIG_PATH and EXAMPLE_CONFIG_PATH.exists():
            config_path = EXAMPLE_CONFIG_PATH
        else:
            raise FileNotFoundError(f"Missing PHP config: {config_path}")
    php_code = (
        "$config = require " + repr(str(config_path)) + "; "
        "echo json_encode($config, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);"
    )
    result = subprocess.run(["php", "-r", php_code], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("PHP config did not return an object")
    return data


def database_config(kind: str = "public") -> dict[str, Any]:
    config = read_php_config()
    db = config.get("db")
    if not isinstance(db, dict):
        raise ValueError("PHP config missing db section")
    database_key = "public_database" if kind == "public" else "library_database"
    return {
        "host": db.get("host", "127.0.0.1"),
        "port": int(db.get("port", 3306)),
        "user": db.get("user", "chronoshelter"),
        "password": db.get("password", ""),
        "database": db.get(database_key),
        "charset": db.get("charset", "utf8mb4"),
    }
