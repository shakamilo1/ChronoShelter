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


def test_export_mapping_converts_downloaded_manifest_to_cached_cover_cache_status():
    assert "THEN 'cached'" in CLI
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
    assert "'downloaded','unchanged','pending_deploy'" in CLI
    assert "THEN 'cached'" in CLI


def test_import_mapping_defaults_to_cached_status():
    assert "'status' => (string) ($row['status'] ?? 'cached')" in CLI
    assert "INSERT INTO cover_cache" in CLI
