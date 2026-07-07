from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app import repositories
from importer.image_cache import cache_cover


def cache_covers(all_items=False, missing=False, anime_id=None, limit=None):
    rows = repositories.iter_covers(missing_only=missing and not all_items, anime_id=anime_id, limit=limit)
    iterable = tqdm(rows, unit="cover") if tqdm else rows
    ok = failed = skipped = 0
    failures: list[str] = []
    for row in iterable:
        local = f"media/covers/{row['id']}.jpg"
        if Path(local).exists() and not all_items:
            skipped += 1
            continue
        path = cache_cover(int(row["id"]))
        if path:
            repositories.update_cover_status(int(row["id"]), path, "cached")
            ok += 1
        else:
            repositories.update_cover_status(int(row["id"]), None, "failed")
            failed += 1
            failures.append(f"{row['id']} https://api.bgm.tv/v0/subjects/{row['id']}/image?type=large")
    if failures:
        log_dir = ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "cover_failures.log").write_text("\n".join(failures) + "\n", encoding="utf-8")
    print(f"cached={ok} skipped={skipped} failed={failed}")
    return ok, skipped, failed


def main():
    parser = argparse.ArgumentParser(description="Cache ChronoShelter cover images without blocking the website.")
    parser.add_argument("--all", action="store_true", help="Process all rows, even if they already have local paths.")
    parser.add_argument("--missing", action="store_true", help="Only process rows missing local cover paths.")
    parser.add_argument("--id", type=int, dest="anime_id")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cache_covers(args.all, args.missing, args.anime_id, args.limit)


if __name__ == "__main__":
    main()
