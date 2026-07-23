from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_placeholder_points_to_php_offline_sync_not_python_cache():
    text = (ROOT / "static" / "img" / "placeholder.svg").read_text(encoding="utf-8")

    assert "tools/cache_covers.py" not in text
    assert "Use offline cover sync" in text
    assert "python tools/download_covers.py sync" in text


def test_readme_uses_remote_filename_partitioned_cover_path_not_old_flat_path():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "covers/{subject_id}.jpg" not in text
    assert "covers/subjects/{level1}/{level2}/{subject_id}_{BangumiSuffix}.{ext}" in text
    assert "cover_cache.local_path" in text
    assert "jpg" in text and "png" in text and "webp" in text
