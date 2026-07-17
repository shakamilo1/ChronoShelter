from importer.image_cache import cache_cover, detect_image_size

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
)


def test_detect_png_size():
    assert detect_image_size(PNG_1X1) == (1, 1)


def test_cache_cover_deduplicates_existing_valid_file(tmp_path):
    covers = tmp_path / "covers"
    covers.mkdir()
    existing = covers / "1.jpg"
    existing.write_bytes(PNG_1X1 + (b"0" * 200))
    assert cache_cover(1, media_root=covers) == str(existing)
    assert existing.read_bytes().startswith(PNG_1X1)
