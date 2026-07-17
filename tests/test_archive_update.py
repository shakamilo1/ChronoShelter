import zipfile

from tools.archive_update import REQUIRED_FILES, prepare_archive


def test_prepare_archive_extracts_valid_zip_atomically(tmp_path, monkeypatch):
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name in REQUIRED_FILES:
            zf.writestr(f"dump/{name}", "{}\n")

    monkeypatch.setattr("tools.archive_update.CURRENT_TMP_DIR", tmp_path / "current_tmp")
    monkeypatch.setattr("tools.archive_update.CURRENT_DIR", tmp_path / "current")

    current = prepare_archive(zip_path)

    assert current == tmp_path / "current"
    for name in REQUIRED_FILES:
        assert (current / name).exists()
    assert not (tmp_path / "current_tmp").exists()
