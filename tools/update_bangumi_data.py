from __future__ import annotations

import argparse
from pathlib import Path

from importer.bangumi_data_sync import check_update, download, replace_from_file


def main():
    parser = argparse.ArgumentParser(description="Manage local bangumi-data data.json cache.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--file", type=Path)
    args = parser.parse_args()
    if args.download:
        target, backup = download()
        print(f"saved={target}")
        if backup:
            print(f"backup={backup}")
    elif args.check:
        check_update()
    elif args.file:
        target, backup = replace_from_file(args.file)
        print(f"saved={target}")
        if backup:
            print(f"backup={backup}")


if __name__ == "__main__":
    main()
