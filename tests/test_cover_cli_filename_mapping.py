from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = (ROOT / "bin" / "bangumi_covers.php").read_text(encoding="utf-8")


def test_cli_preserves_safe_bangumi_remote_filename_and_hash_fallback():
    assert "function safe_remote_filename" in CLI
    assert "_[A-Za-z0-9_-]+" in CLI
    assert "parse_url($url, PHP_URL_PATH)" in CLI
    assert "rawurldecode(basename($path))" in CLI
    assert "substr(hash('sha256', $url), 0, 12)" in CLI


def test_cli_records_remote_filename_and_mapping_fields():
    assert "remote_filename TEXT NULL" in CLI
    assert "remote_filename = :remote_filename" in CLI
    assert "source_url" in CLI
    assert "sha256" in CLI


def test_cli_rejects_extension_mismatch_and_does_not_silently_swallow_mysql_mapping():
    assert "remote filename extension does not match detected image type" in CLI
    assert "mapping_failed" in CLI
    assert "catch (Throwable) {\n        // MySQL cache is optional" not in CLI


def test_cli_supports_mapping_export_and_import():
    assert "export-mapping" in CLI
    assert "import-mapping" in CLI
    assert "cover-mapping-" in CLI


def test_export_mapping_converts_successful_manifest_file_to_cached_cover_cache_status():
    assert "$export['status'] = 'cached'" in CLI
    assert "downloaded_url AS source_url" in CLI
    assert "relative_path AS local_path" in CLI


def test_offline_download_does_not_require_mysql_by_default():
    assert "'write-mysql' => false" in CLI
    apply_block = CLI[CLI.index("function apply_one"):CLI.index("function sync_mysql_cover_cache")]
    assert "pending_deploy" in apply_block
    assert "if ((bool) $GLOBALS['cover_sync_options']['write-mysql'])" in apply_block
    assert "sync_mysql_cover_cache" in apply_block


def test_mapping_failed_only_when_explicit_mysql_write_requested():
    apply_block = CLI[CLI.index("function apply_one"):CLI.index("function sync_mysql_cover_cache")]
    mapping_failed_pos = apply_block.index("mapping_failed")
    write_mysql_pos = apply_block.index("write-mysql")
    assert write_mysql_pos < mapping_failed_pos


def test_export_mapping_converts_pending_deploy_to_cached_cover_cache_status():
    assert "local_cover_ok($row['local_path'], $row)" in CLI
    assert "$export['status'] = 'cached'" in CLI


def test_import_mapping_writes_cached_status_for_cached_rows():
    assert "'status' => 'cached'" in CLI
    assert "INSERT INTO cover_cache" in CLI


def test_export_mapping_uses_valid_existing_success_file_for_transient_statuses():
    assert "local_cover_ok($row['local_path'], $row)" in CLI
    assert "$export['status'] = 'cached'" in CLI
    assert "pending_update" not in CLI[CLI.index("function export_mapping"):CLI.index("function import_mapping_row_is_safe")]
    assert "remote_missing" not in CLI[CLI.index("function export_mapping"):CLI.index("function import_mapping_row_is_safe")]


def test_apply_one_never_deletes_old_cover_files_automatically():
    apply_block = CLI[CLI.index("function apply_one"):CLI.index("function sync_mysql_cover_cache")]
    assert "unlink($oldAbsolute)" not in apply_block
    assert "Keep previous cover files" in apply_block


def test_import_mapping_prechecks_before_transaction_and_rolls_back():
    import_block = CLI[CLI.index("function import_mapping"):CLI.index("function cleanup_covers")]
    assert "import_mapping_row_is_safe" in CLI
    assert "beginTransaction()" in import_block
    assert "rollBack()" in import_block
    assert import_block.index("import_mapping_row_is_safe") < import_block.index("beginTransaction()")
    assert "duplicate subject_id" in import_block
    assert "no_cover" in import_block


def test_cleanup_covers_is_dry_run_unless_apply_is_explicit():
    cleanup_block = CLI[CLI.index("function cleanup_covers"):CLI.index("function print_stats")]
    assert "cleanup_candidate" in cleanup_block
    assert "if ((bool) $options['apply'])" in cleanup_block
