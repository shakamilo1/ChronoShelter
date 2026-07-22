import base64

from importer.image_cache import (
    cache_cover,
    cache_cover_with_metadata,
    cover_candidate_paths,
    cover_path,
    detect_image_size,
)

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
)

JPEG_3X2 = bytes.fromhex(
    "FFD8FFE000104A46494600010100000100010000"
    "FFC00011080002000303012200021101031101FFD9"
)

WEBP_1X1 = base64.b64decode("UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA")


def write_partitioned(media_root, subject_id, extension, data):
    path = cover_candidate_paths(subject_id, media_root)[{"jpg": 0, "png": 1, "webp": 2}[extension]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_detect_png_size():
    assert detect_image_size(PNG_1X1) == (1, 1)


def test_detect_jpeg_size():
    assert detect_image_size(JPEG_3X2) == (3, 2)


def test_detect_webp_size():
    assert detect_image_size(WEBP_1X1) == (1, 1)


def test_cache_cover_finds_partitioned_jpeg(tmp_path):
    covers = tmp_path / "covers"
    expected = write_partitioned(covers, 1424, "jpg", JPEG_3X2)

    result = cache_cover_with_metadata(1424, media_root=covers)

    assert result.ok is True
    assert result.status == "cached"
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (3, 2)
    assert cache_cover(1424, media_root=covers) == str(expected)


def test_cache_cover_finds_partitioned_png(tmp_path):
    covers = tmp_path / "covers"
    expected = write_partitioned(covers, 491569, "png", PNG_1X1)

    result = cache_cover_with_metadata(491569, media_root=covers)

    assert result.ok is True
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (1, 1)


def test_cache_cover_finds_partitioned_webp(tmp_path):
    covers = tmp_path / "covers"
    expected = write_partitioned(covers, 491569, "webp", WEBP_1X1)

    result = cache_cover_with_metadata(491569, media_root=covers)

    assert result.ok is True
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (1, 1)


def test_subject_over_one_million_uses_php_partition_algorithm(tmp_path):
    covers = tmp_path / "covers"

    assert cover_path(1234567, media_root=covers) == covers / "subjects" / "001" / "234" / "1234567.jpg"


def test_missing_cover_is_disabled_without_creating_files(tmp_path):
    covers = tmp_path / "covers"

    result = cache_cover_with_metadata(999, media_root=covers)

    assert result.ok is False
    assert result.status == "disabled"
    assert "php bin/bangumi_covers.php sync --resume" in (result.error or "")
    assert not covers.exists()


def test_legacy_flat_file_is_read_only_compatible(tmp_path):
    covers = tmp_path / "covers"
    covers.mkdir()
    legacy = covers / "1.jpg"
    legacy.write_bytes(PNG_1X1 + (b"0" * 200))

    assert cache_cover(1, media_root=covers) == str(legacy)
    assert legacy.read_bytes().startswith(PNG_1X1)


def test_partitioned_file_takes_priority_over_legacy_flat_file(tmp_path):
    covers = tmp_path / "covers"
    covers.mkdir()
    legacy = covers / "1424.jpg"
    legacy.write_bytes(PNG_1X1 + (b"0" * 200))
    partitioned = write_partitioned(covers, 1424, "jpg", JPEG_3X2)

    result = cache_cover_with_metadata(1424, media_root=covers)

    assert result.ok is True
    assert result.local_path == str(partitioned)
    assert legacy.exists()
