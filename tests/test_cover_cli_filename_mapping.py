from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = (ROOT / "bin" / "bangumi_covers.php").read_text(encoding="utf-8")
PYTHON = (ROOT / "tools" / "download_covers.py").read_text(encoding="utf-8")


def test_php_cli_is_import_mapping_only_and_has_no_bangumi_network_sync():
    assert "function import_mapping" in CLI
    assert "function fetch_subject_page" not in CLI
    assert "function download_image_to_tmp" not in CLI
    assert "function apply_updates" not in CLI
    assert "function deep_check" not in CLI
    assert "BANGUMI_SUBJECTS_API" not in CLI
    assert "api.bgm.tv" not in CLI
    assert "lain.bgm.tv" not in CLI
    assert "PHP cover command is disabled on NAS" in CLI


def test_php_import_mapping_validates_file_fields_and_uses_transaction():
    assert "function import_mapping_row_is_safe" in CLI
    assert "no_cover mapping must not include file fields" in CLI
    assert "remote_filename" in CLI
    assert "sha256" in CLI
    assert "beginTransaction" in CLI
    assert "rollBack" in CLI
    assert "commit" in CLI


def test_python_syncer_owns_bangumi_api_filename_mapping_and_export():
    assert '"https://api.bgm.tv/v0/subjects"' in PYTHON
    assert "SUBJECT_TYPE = 2" in PYTHON
    assert "PAGE_LIMIT = 50" in PYTHON
    assert "def safe_remote_filename" in PYTHON
    assert "def cover_relative_path" in PYTHON
    assert "def export_mapping" in PYTHON
    assert "def sync" in PYTHON
    assert "def verify_files" in PYTHON
