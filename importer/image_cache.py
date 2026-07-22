from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from struct import unpack

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = PROJECT_ROOT / "covers"


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


def cover_partition_prefix(subject_id: int) -> Path:
    level1 = f"{subject_id // 1_000_000:03d}"
    level2 = f"{(subject_id % 1_000_000) // 1_000:03d}"
    return Path("subjects") / level1 / level2


def cover_partition_relative_path(subject_id: int, filename: str) -> Path:
    return cover_partition_prefix(subject_id) / filename


def cover_path(subject_id: int, media_root: Path = MEDIA_ROOT, local_path: str | None = None) -> Path:
    """Resolve an explicitly supplied local_path; never guess current covers."""
    if local_path is None:
        raise ValueError("local_path is required")
    return media_root / safe_relative_path(subject_id, local_path)


def safe_relative_path(subject_id: int, local_path: str) -> Path:
    normalized = local_path.replace("\\", "/").strip("/")
    if normalized.startswith("covers/"):
        normalized = normalized[len("covers/"):]
    if not normalized or ".." in normalized or any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise ValueError("unsafe cover local_path")
    filename = Path(normalized).name
    if "/" in filename or "\\" in filename:
        raise ValueError("unsafe cover filename")
    allowed = (".jpg", ".jpeg", ".png", ".webp")
    if not filename.lower().endswith(allowed):
        raise ValueError("unsupported cover extension")
    if normalized == f"{subject_id}{Path(filename).suffix}":
        return Path(normalized)
    expected_prefix = str(cover_partition_prefix(subject_id)).replace("\\", "/") + "/"
    if not normalized.startswith(expected_prefix):
        raise ValueError("cover path shard does not match subject_id")
    stem = Path(filename).stem
    if not stem.startswith(f"{subject_id}_"):
        raise ValueError("cover filename does not match subject_id")
    suffix = stem[len(str(subject_id)) + 1:]
    if not suffix or any(not (ch.isalnum() or ch in "_-") for ch in suffix):
        raise ValueError("unsafe cover filename suffix")
    return Path(normalized)


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
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        return unpack("<H", data[26:28])[0] & 0x3FFF, unpack("<H", data[28:30])[0] & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def detect_image_size(data: bytes) -> tuple[int, int] | None:
    return _png_size(data) or _jpeg_size(data) or _webp_size(data)


def cache_cover_with_metadata(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20, local_path: str | None = None) -> CoverCacheResult:  # noqa: ARG001
    """Validate one explicit local_path without network access.

    The current cover mapping must come from cover_cache.local_path or an export
    manifest. This compatibility helper deliberately does not scan subject_id
    variants to guess the current cover.
    """
    if local_path is None:
        return CoverCacheResult(subject_id=subject_id, ok=False, status="disabled", error="local_path is required; use php bin/bangumi_covers.php sync --resume")
    try:
        path = cover_path(subject_id, media_root, local_path)
    except ValueError as exc:
        return CoverCacheResult(subject_id=subject_id, ok=False, status="invalid", error=str(exc))
    if not path.exists() or path.stat().st_size <= 0:
        return CoverCacheResult(subject_id=subject_id, ok=False, status="disabled", error="local cover file is missing; use php bin/bangumi_covers.php sync --resume")
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


def cache_cover(subject_id: int, image_type: str = "large", media_root: Path = MEDIA_ROOT, timeout: int = 20, local_path: str | None = None) -> str | None:
    result = cache_cover_with_metadata(subject_id, image_type=image_type, media_root=media_root, timeout=timeout, local_path=local_path)
    return result.local_path if result.ok else None
