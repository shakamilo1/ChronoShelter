from importer.image_cache import cache_cover


def test_cache_cover_deduplicates_existing_file(tmp_path):
    covers = tmp_path / "covers"
    covers.mkdir()
    existing = covers / "1.jpg"
    existing.write_bytes(b"old")
    assert cache_cover(1, "http://invalid.local/image.jpg", media_root=covers) == str(existing)
    assert existing.read_bytes() == b"old"
