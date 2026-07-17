from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = ROOT / "data" / "archive"
DOWNLOADS_DIR = ARCHIVE_ROOT / "downloads"
CURRENT_DIR = ARCHIVE_ROOT / "current"
CURRENT_TMP_DIR = ARCHIVE_ROOT / "current_tmp"

REQUIRED_FILES = [
    "subject.jsonlines",
    "episode.jsonlines",
    "person.jsonlines",
    "character.jsonlines",
    "subject-persons.jsonlines",
    "subject-characters.jsonlines",
    "subject-relations.jsonlines",
    "person-characters.jsonlines",
    "person-relations.jsonlines",
]


def _safe_member_path(root: Path, member_name: str) -> Path:
    target = (root / member_name).resolve()
    root_resolved = root.resolve()
    if not str(target).startswith(str(root_resolved)):
        raise ValueError(f"unsafe zip member path: {member_name}")
    return target


def download_release(url: str, downloads_dir: Path = DOWNLOADS_DIR) -> Path:
    downloads_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    filename = Path(parsed.path).name or f"archive_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    if not filename.endswith(".zip"):
        filename += ".zip"
    dest = downloads_dir / filename
    req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
    with urlopen(req, timeout=120) as response:  # noqa: S310 - operator-provided release URL
        dest.write_bytes(response.read())
    return dest


def extract_zip_to_tmp(zip_path: Path, tmp_dir: Path = CURRENT_TMP_DIR) -> Path:
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                _safe_member_path(tmp_dir, member.filename).mkdir(parents=True, exist_ok=True)
                continue
            target = _safe_member_path(tmp_dir, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    return tmp_dir


def _find_archive_root(extracted_dir: Path) -> Path:
    if all((extracted_dir / name).exists() for name in REQUIRED_FILES):
        return extracted_dir
    candidates = [path for path in extracted_dir.rglob("subject.jsonlines")]
    for subject_file in candidates:
        candidate = subject_file.parent
        if all((candidate / name).exists() for name in REQUIRED_FILES):
            return candidate
    return extracted_dir


def validate_archive_files(extracted_dir: Path) -> tuple[bool, Path, list[str]]:
    archive_root = _find_archive_root(extracted_dir)
    missing = [name for name in REQUIRED_FILES if not (archive_root / name).exists()]
    return not missing, archive_root, missing


def activate_current(tmp_dir: Path = CURRENT_TMP_DIR, current_dir: Path = CURRENT_DIR) -> Path:
    valid, archive_root, missing = validate_archive_files(tmp_dir)
    if not valid:
        raise RuntimeError(f"Archive validation failed; missing files: {', '.join(missing)}")
    backup = None
    if current_dir.exists():
        backup = current_dir.with_name(f"current_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
        current_dir.rename(backup)
    if archive_root == tmp_dir:
        tmp_dir.rename(current_dir)
    else:
        if current_dir.exists():
            shutil.rmtree(current_dir)
        shutil.copytree(archive_root, current_dir)
        shutil.rmtree(tmp_dir)
    if backup:
        shutil.rmtree(backup)
    return current_dir


def version_info(zip_path: Path, archive_root: Path) -> dict[str, str | int]:
    return {
        "zip": str(zip_path),
        "archive_dir": str(archive_root),
        "required_files": len(REQUIRED_FILES),
        "zip_size": zip_path.stat().st_size if zip_path.exists() else 0,
    }


def prepare_archive(zip_path: Path) -> Path:
    tmp_dir = extract_zip_to_tmp(zip_path, CURRENT_TMP_DIR)
    valid, archive_root, missing = validate_archive_files(tmp_dir)
    if not valid:
        raise SystemExit(f"missing required Archive files: {', '.join(missing)}")
    current = activate_current(tmp_dir, CURRENT_DIR)
    info = version_info(zip_path, current)
    for key, value in info.items():
        print(f"{key}={value}")
    print(f"current={current}")
    return current


def latest_placeholder():
    print("--latest is reserved for future latest.json support.")
    print("For now, pass --url <release.zip> or --file archive.zip.")


def main():
    parser = argparse.ArgumentParser(description="Prepare a Bangumi Archive release zip without importing it into the database.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Local Bangumi Archive release zip.")
    source.add_argument("--url", help="Bangumi Archive release zip URL.")
    source.add_argument("--latest", action="store_true", help="Reserved for future latest.json release discovery.")
    args = parser.parse_args()

    if args.latest:
        latest_placeholder()
        return
    if args.url:
        zip_path = download_release(args.url)
        print(f"downloaded={zip_path}")
    else:
        zip_path = args.file
    prepare_archive(zip_path)


if __name__ == "__main__":
    main()
