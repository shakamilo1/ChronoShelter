import base64

from importer.image_cache import (
    cache_cover,
    cache_cover_with_metadata,
    cover_path,
    detect_image_size,
    safe_relative_path,
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


def write_explicit(media_root, local_path, data):
    path = media_root / local_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_detect_png_size():
    assert detect_image_size(PNG_1X1) == (1, 1)


def test_detect_jpeg_size():
    assert detect_image_size(JPEG_3X2) == (3, 2)


def test_detect_webp_size():
    assert detect_image_size(WEBP_1X1) == (1, 1)


def test_cache_cover_validates_explicit_partitioned_jpeg(tmp_path):
    covers = tmp_path / "covers"
    local_path = "subjects/000/001/1424_Ewjo.jpg"
    expected = write_explicit(covers, local_path, JPEG_3X2)

    result = cache_cover_with_metadata(1424, media_root=covers, local_path=local_path)

    assert result.ok is True
    assert result.status == "cached"
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (3, 2)
    assert cache_cover(1424, media_root=covers, local_path=local_path) == str(expected)


def test_cache_cover_validates_explicit_png(tmp_path):
    covers = tmp_path / "covers"
    local_path = "subjects/000/491/491569_xxxxx.png"
    expected = write_explicit(covers, local_path, PNG_1X1)

    result = cache_cover_with_metadata(491569, media_root=covers, local_path=local_path)

    assert result.ok is True
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (1, 1)


def test_cache_cover_validates_explicit_webp(tmp_path):
    covers = tmp_path / "covers"
    local_path = "subjects/000/491/491569_xxxxx.webp"
    expected = write_explicit(covers, local_path, WEBP_1X1)

    result = cache_cover_with_metadata(491569, media_root=covers, local_path=local_path)

    assert result.ok is True
    assert result.local_path == str(expected)
    assert (result.width, result.height) == (1, 1)


def test_subject_over_one_million_uses_php_partition_algorithm(tmp_path):
    covers = tmp_path / "covers"
    local_path = "subjects/001/234/1234567_xxxxx.jpg"

    assert cover_path(1234567, media_root=covers, local_path=local_path) == covers / local_path


def test_missing_cover_is_disabled_without_creating_files(tmp_path):
    covers = tmp_path / "covers"

    result = cache_cover_with_metadata(999, media_root=covers)

    assert result.ok is False
    assert result.status == "disabled"
    assert "php bin/bangumi_covers.php sync --resume" in (result.error or "")
    assert not covers.exists()


def test_legacy_flat_file_is_read_only_when_explicitly_mapped(tmp_path):
    covers = tmp_path / "covers"
    legacy = write_explicit(covers, "1.jpg", PNG_1X1 + (b"0" * 200))

    assert cache_cover(1, media_root=covers, local_path="1.jpg") == str(legacy)
    assert legacy.read_bytes().startswith(PNG_1X1)


def test_partitioned_file_is_used_only_when_database_mapping_points_to_it(tmp_path):
    covers = tmp_path / "covers"
    legacy = write_explicit(covers, "1424.jpg", PNG_1X1 + (b"0" * 200))
    partitioned = write_explicit(covers, "subjects/000/001/1424_Ewjo.jpg", JPEG_3X2)

    result = cache_cover_with_metadata(1424, media_root=covers, local_path="subjects/000/001/1424_Ewjo.jpg")

    assert result.ok is True
    assert result.local_path == str(partitioned)
    assert cache_cover(1424, media_root=covers, local_path="1424.jpg") == str(legacy)


def test_rejects_wrong_subject_prefix_and_traversal_paths():
    bad_paths = [
        "subjects/000/001/9999_Ewjo.jpg",
        "subjects/000/001/1424.jpg",
        "subjects/000/002/1424_Ewjo.jpg",
        "subjects/000/001/1424_../Ewjo.jpg",
        "subjects/000/001/1424_%2e%2e.jpg",
        "../covers/1424_Ewjo.jpg",
    ]
    for local_path in bad_paths:
        try:
            safe_relative_path(1424, local_path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe path accepted: {local_path}")
