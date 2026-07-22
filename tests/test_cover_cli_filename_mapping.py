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
