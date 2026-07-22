"""Deprecated cover downloader.

Bangumi covers are no longer downloaded through the legacy per-subject image
API. Use the PHP offline synchronizer instead:

    php bin/bangumi_covers.php sync --resume

This stub is intentionally kept so old automation fails safely instead of
contacting api.bgm.tv/v0/subjects/{id}/image or lain.bgm.tv during migration.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "tools/download_covers.py is deprecated and disabled. "
    "Use: php bin/bangumi_covers.php sync --resume"
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
