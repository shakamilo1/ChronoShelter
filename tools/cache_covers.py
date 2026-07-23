"""Deprecated cover cache entry point.

Cover maintenance is handled by the PHP offline Bangumi animation cover sync
system. This legacy Python wrapper is disabled to prevent accidental use of the
old per-subject Bangumi image API.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "tools/cache_covers.py is deprecated and disabled. "
    "Use: python tools/download_covers.py sync --resume"
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
