from __future__ import annotations

from pathlib import Path

from importer.import_archive_dump import import_jsonlines_file


def import_file(path, limit=None, dry_run=False, only_id=None, safe_mode=False, bangumi_data_file=None, cache_images=False):
    # Compatibility shim for older tests/scripts. Prefer importer/import_archive_dump.py.
    # Filtering by only_id is intentionally not implemented in this shim.
    return (*import_jsonlines_file(Path(path), "subjects", limit=limit, dry_run=dry_run), 0)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compatibility subject importer; prefer import_archive_dump.py")
    parser.add_argument("--file", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--id", type=int, dest="only_id")
    args = parser.parse_args()
    imported, skipped, errors = import_file(args.file, args.limit, args.dry_run, args.only_id)
    print(f"imported={imported} skipped={skipped} errors={errors}")


if __name__ == "__main__":
    main()
