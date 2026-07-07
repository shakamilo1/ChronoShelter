from __future__ import annotations

from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media" / "covers"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def cover_path(anime_id: int, media_root: Path = MEDIA_ROOT) -> Path:
    return media_root / f"{anime_id}.jpg"


def cache_cover(anime_id: int, url: str | None, media_root: Path = MEDIA_ROOT, timeout: int = 15) -> str | None:
    if not url:
        return None
    path = cover_path(anime_id, media_root)
    if path.exists() and path.stat().st_size > 0:
        return _display_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - user-provided cache URL
            path.write_bytes(response.read())
    except (OSError, URLError, TimeoutError):
        return None
    return _display_path(path)
