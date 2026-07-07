from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/bangumi-data/bangumi-data/master/dist/data.json"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "bangumi-data"
DATA_FILE = DATA_DIR / "data.json"
BACKUP_DIR = DATA_DIR / "backups"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _backup_existing() -> Path | None:
    if not DATA_FILE.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"data_{stamp}.json"
    shutil.copy2(DATA_FILE, backup)
    return backup


def _validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as fh:
        json.load(fh)


def replace_from_file(source: Path) -> tuple[Path, Path | None]:
    _validate_json(source)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    backup = _backup_existing()
    shutil.copy2(source, DATA_FILE)
    return DATA_FILE, backup


def download(url: str = DEFAULT_SOURCE_URL) -> tuple[Path, Path | None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "bangumi_data.download.tmp"
    req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
    with urlopen(req, timeout=60) as response:  # noqa: S310 - fixed default URL or explicit CLI URL
        tmp.write_bytes(response.read())
    try:
        return replace_from_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def check_update(url: str = DEFAULT_SOURCE_URL) -> bool:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "bangumi_data.check.tmp"
    req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
    with urlopen(req, timeout=60) as response:  # noqa: S310 - fixed default URL or explicit CLI URL
        tmp.write_bytes(response.read())
    try:
        local_hash = _sha256(DATA_FILE)
        remote_hash = _sha256(tmp)
        changed = local_hash != remote_hash
        print(f"local_sha256={local_hash or 'missing'}")
        print(f"remote_sha256={remote_hash}")
        print("update_available=true" if changed else "update_available=false")
        return changed
    finally:
        tmp.unlink(missing_ok=True)


def load_entries(path: Path = DATA_FILE) -> dict[int, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    entries: dict[int, dict] = {}
    for item in items or []:
        bgm_id = item.get("bgm_id") or item.get("id")
        if bgm_id:
            entries[int(bgm_id)] = item
    return entries


def main():
    parser = argparse.ArgumentParser(description="Sync bangumi-data dist/data.json without touching the main database.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", action="store_true", help="Download the latest bangumi-data data.json.")
    group.add_argument("--file", type=Path, help="Replace local bangumi-data with a manually provided data.json.")
    group.add_argument("--check-update", action="store_true", help="Download and compare hashes without replacing local data.")
    parser.add_argument("--url", default=DEFAULT_SOURCE_URL, help="Override source URL for download/check-update.")
    args = parser.parse_args()

    if args.download:
        target, backup = download(args.url)
        print(f"saved={target}")
        if backup:
            print(f"backup={backup}")
    elif args.file:
        target, backup = replace_from_file(args.file)
        print(f"saved={target}")
        if backup:
            print(f"backup={backup}")
    elif args.check_update:
        check_update(args.url)


if __name__ == "__main__":
    main()
