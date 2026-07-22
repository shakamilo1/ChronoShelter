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
    assert "cleanup-covers --apply is disabled" in cleanup_block
    assert "unlink(" not in cleanup_block


def test_official_api_limit_and_paged_subject_validation():
    assert "const PAGE_LIMIT = 50" in CLI
    assert "total" in CLI and "offset" in CLI and "data" in CLI
    assert "Bangumi API returned empty data before total was reached" in CLI
    assert "Bangumi API returned unexpected offset" in CLI


def test_no_icon_subject_is_treated_as_no_cover_without_binary_name_search():
    assert "function subject_large_image_url" in CLI
    assert "no_icon_subject.png" in CLI
    assert "str_contains($data, 'no_icon_subject')" not in CLI


def test_resume_cursor_advances_per_consumed_api_record():
    scan_block = CLI[CLI.index("function scan_pages"):CLI.index("function write_report")]
    assert "$offset++;" in scan_block
    assert "update_run($run['run_id'], $offset, $total, 'running')" in scan_block
    assert "PAGE_LIMIT" not in scan_block.split("$offset++;")[-1].split("update_run")[0]


def test_versioned_local_filename_for_same_remote_name_different_sha():
    apply_block = CLI[CLI.index("function apply_one"):CLI.index("function sync_mysql_cover_cache")]
    assert "--' . substr($meta['sha256'], 0, 12)" in apply_block
    assert "$existingSha === $meta['sha256']" in apply_block
    assert "(?:--[a-f0-9]{12})?" in CLI
