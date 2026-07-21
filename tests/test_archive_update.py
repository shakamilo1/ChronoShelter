import zipfile

from tools.archive_update import REQUIRED_FILES, prepare_archive


def test_prepare_archive_extracts_valid_zip_atomically(tmp_path, monkeypatch):
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name in REQUIRED_FILES:
            zf.writestr(f"dump/{name}", "{}\n")

    monkeypatch.setattr("tools.archive_update.EXTRACTED_DIR", tmp_path / "extracted")
    monkeypatch.setattr("tools.archive_update.PROCESSED_DIR", tmp_path / "processed")

    processed = prepare_archive(zip_path)

    assert processed == tmp_path / "processed"
    for name in REQUIRED_FILES:
        assert (processed / name).exists()
    assert not (tmp_path / "extracted").exists()
