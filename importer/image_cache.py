from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from struct import unpack

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = PROJECT_ROOT / "covers"
SUPPORTED_EXTENSIONS = ("jpg", "png", "webp")


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


def cover_partition_relative_path(subject_id: int, extension: str) -> Path:
    level1 = f"{subject_id // 1_000_000:03d}"
    level2 = f"{(subject_id % 1_000_000) // 1_000:03d}"
    return Path("subjects") / level1 / level2 / f"{subject_id}.{extension}"


def cover_path(subject_id: int, media_root: Path = MEDIA_ROOT) -> Path:
    """Return the preferred partitioned JPEG path for compatibility."""
    return media_root / cover_partition_relative_path(subject_id, "jpg")


def cover_candidate_paths(subject_id: int, media_root: Path = MEDIA_ROOT) -> list[Path]:
    """Return local-only cover candidates, preferring PHP sync partition paths."""
    partitioned = [media_root / cover_partition_relative_path(subject_id, ext) for ext in SUPPORTED_EXTENSIONS]
    legacy = [media_root / f"{subject_id}.jpg"]
    return partitioned + legacy


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


def _webp_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = unpack("<H", data[26:28])[0] & 0x3FFF
        height = unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None


def detect_image_size(data: bytes) -> tuple[int, int] | None:
    return _png_size(data) or _jpeg_size(data) or _webp_size(data)


def _local_cover_result(subject_id: int, path: Path) -> CoverCacheResult:
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


def cache_cover_with_metadata(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20) -> CoverCacheResult:  # noqa: ARG001
    """Return metadata for an existing local cover without network access.

    The historical importer helper used Bangumi's per-subject image endpoint.
    Runtime and importer code must no longer download covers this way; use
    ``php bin/bangumi_covers.php sync --resume`` on a maintenance machine.
    This function is kept only for callers/tests that need to validate an
    already-present local file. It checks PHP-sync partitioned covers first and
    then a read-only legacy flat ``{subject_id}.jpg`` file for compatibility.
    """
    for path in cover_candidate_paths(subject_id, media_root):
        if path.exists() and path.stat().st_size > 0:
            return _local_cover_result(subject_id, path)
    return CoverCacheResult(
        subject_id=subject_id,
        ok=False,
        status="disabled",
        error="online cover downloads are disabled; use php bin/bangumi_covers.php sync --resume",
    )


def cache_cover(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20) -> str | None:
    result = cache_cover_with_metadata(subject_id, image_type=image_type, media_root=media_root, timeout=timeout)
    return result.local_path if result.ok else None
