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


def test_docs_describe_windows_php_import_and_no_nas_import_command():
    docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ["README.md", "docs/deployment.md", "docs/bangumi_cover_sync.md"]
    )

    assert "Windows PHP" in docs
    assert "连接 NAS MariaDB" in docs
    assert "NAS 只提供" in docs
    forbidden = [
        "在 NAS 上导入映射",
        "随后在 NAS 上",
        "NAS 上只运行",
        "由 NAS/PHP 导入",
        "NAS/PHP 只验证",
        "正式服务器运行 `php bin/bangumi_covers.php import-mapping",
    ]
    for phrase in forbidden:
        assert phrase not in docs


def test_docs_do_not_require_cover_cache_mapping_migration():
    docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ["README.md", "docs/deployment.md", "docs/bangumi_cover_sync.md"]
    )
    install_check = (ROOT / "install_check.php").read_text(encoding="utf-8")

    assert "sql/migrations/003_cover_cache_mapping_columns.sql" not in docs
    assert "sql/migrations/003_cover_cache_mapping_columns.sql" not in install_check
    assert "004_add_subjects_pagination_indexes.sql" in docs
