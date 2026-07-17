from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from struct import unpack
from urllib.error import URLError
from urllib.request import Request, urlopen

MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media" / "covers"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_API = "https://api.bgm.tv/v0/subjects/{subject_id}/image?type={image_type}"
REJECTED_URLS = {"https://lain.bgm.tv/img/no_icon_subject.png"}
MIN_IMAGE_BYTES = 128


@dataclass
class CoverCacheResult:
    subject_id: int
    ok: bool
    local_path: str | None = None
    status: str = "failed"
    error: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def cover_path(subject_id: int, media_root: Path = MEDIA_ROOT) -> Path:
    return media_root / f"{subject_id}.jpg"


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in {0xD8, 0xD9}:
            continue
        if i + 2 > len(data):
            return None
        length = unpack(">H", data[i:i + 2])[0]
        if marker in range(0xC0, 0xC4):
            if i + 7 > len(data):
                return None
            height = unpack(">H", data[i + 3:i + 5])[0]
            width = unpack(">H", data[i + 5:i + 7])[0]
            return width, height
        i += length
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = unpack(">I", data[16:20])[0]
        height = unpack(">I", data[20:24])[0]
        return width, height
    return None


def detect_image_size(data: bytes) -> tuple[int, int] | None:
    return _png_size(data) or _jpeg_size(data)


def cache_cover_with_metadata(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20) -> CoverCacheResult:
    path = cover_path(subject_id, media_root)
    if path.exists() and path.stat().st_size > 0:
        data = path.read_bytes()
        size = detect_image_size(data)
        return CoverCacheResult(
            subject_id=subject_id,
            ok=bool(size),
            local_path=_display_path(path) if size else None,
            status="cached" if size else "invalid",
            error=None if size else "cached file is not a supported image",
            file_size=len(data),
            width=size[0] if size else None,
            height=size[1] if size else None,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    url = IMAGE_API.format(subject_id=subject_id, image_type=image_type)
    try:
        req = Request(url, headers={"User-Agent": "ChronoShelter/1.0"})
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - fixed Bangumi image API
            http_status = getattr(response, "status", None)
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except (OSError, URLError, TimeoutError) as exc:
        return CoverCacheResult(subject_id=subject_id, ok=False, error=str(exc))

    if http_status != 200:
        return CoverCacheResult(subject_id=subject_id, ok=False, http_status=http_status, content_type=content_type, error="unexpected HTTP status")
    if final_url in REJECTED_URLS:
        return CoverCacheResult(subject_id=subject_id, ok=False, http_status=http_status, content_type=content_type, error="rejected no-icon placeholder")
    if not content_type.lower().startswith("image/"):
        return CoverCacheResult(subject_id=subject_id, ok=False, http_status=http_status, content_type=content_type, file_size=len(data), error="unexpected content type")
    if len(data) < MIN_IMAGE_BYTES:
        return CoverCacheResult(subject_id=subject_id, ok=False, http_status=http_status, content_type=content_type, file_size=len(data), error="image file too small")
    size = detect_image_size(data)
    if not size:
        return CoverCacheResult(subject_id=subject_id, ok=False, http_status=http_status, content_type=content_type, file_size=len(data), error="cannot detect image dimensions")
    path.write_bytes(data)
    return CoverCacheResult(subject_id=subject_id, ok=True, local_path=_display_path(path), status="cached", http_status=http_status, content_type=content_type, file_size=len(data), width=size[0], height=size[1])


def cache_cover(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20) -> str | None:
    result = cache_cover_with_metadata(subject_id, image_type=image_type, media_root=media_root, timeout=timeout)
    return result.local_path if result.ok else None
