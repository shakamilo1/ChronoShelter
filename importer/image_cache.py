from __future__ import annotations

from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media" / "covers"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_API = "https://api.bgm.tv/v0/subjects/{subject_id}/image?type={image_type}"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def cover_path(subject_id: int, media_root: Path = MEDIA_ROOT) -> Path:
    return media_root / f"{subject_id}.jpg"


def cache_cover(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20) -> str | None:
    path = cover_path(subject_id, media_root)
    if path.exists() and path.stat().st_size > 0:
        return _display_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = IMAGE_API.format(subject_id=subject_id, image_type=image_type)
    try:
        req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - fixed Bangumi image API
            path.write_bytes(response.read())
    except (OSError, URLError, TimeoutError):
        return None
    return _display_path(path)
