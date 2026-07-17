from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app import repositories
from importer.image_cache import cache_cover_with_metadata


def cache_covers(all_items=False, missing=False, anime_id=None, limit=None, retry_failed=False):
    if retry_failed:
        rows = repositories.failed_cover_ids(limit=limit)
    else:
        rows = repositories.iter_covers(missing_only=missing and not all_items, anime_id=anime_id, limit=limit)
    iterable = tqdm(rows, unit="cover") if tqdm else rows
    ok = failed = skipped = 0
    failures: list[str] = []
    for row in iterable:
        subject_id = int(row["id"])
        local = ROOT / "media" / "covers" / f"{subject_id}.jpg"
        if local.exists() and not all_items and not retry_failed:
            skipped += 1
            continue
        result = cache_cover_with_metadata(subject_id)
        repositories.update_cover_status(subject_id, result.local_path, result.status, asdict(result))
        if result.ok:
            ok += 1
        else:
            failed += 1
            failures.append(f"{subject_id} {result.error or 'unknown error'}")
    if failures:
        log_dir = ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "cover_failures.log").write_text("\n".join(failures) + "\n", encoding="utf-8")
    print(f"cached={ok} skipped={skipped} failed={failed}")
    return ok, skipped, failed


def main():
    parser = argparse.ArgumentParser(description="Cache ChronoShelter cover images without blocking the website.")
    parser.add_argument("--all", action="store_true", help="Process all subjects, even if local files exist.")
    parser.add_argument("--missing", action="store_true", help="Process subjects missing local cover files.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry subjects recorded as failed in chrono_library.cover_cache.")
    parser.add_argument("--id", type=int, dest="anime_id")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cache_covers(args.all, args.missing, args.anime_id, args.limit, args.retry_failed)


if __name__ == "__main__":
    main()
