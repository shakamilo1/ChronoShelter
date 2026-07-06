import json

from importer.bangumi_data_sync import load_entries, replace_from_file


def test_replace_from_file_keeps_backup(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = data_dir / "bangumi_data.json"
    backup_dir = data_dir / "backups"
    monkeypatch.setattr("importer.bangumi_data_sync.DATA_DIR", data_dir)
    monkeypatch.setattr("importer.bangumi_data_sync.DATA_FILE", target)
    monkeypatch.setattr("importer.bangumi_data_sync.BACKUP_DIR", backup_dir)

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps([{"bgm_id": 1, "title": "old"}]), encoding="utf-8")
    second.write_text(json.dumps([{"bgm_id": 1, "title": "new"}]), encoding="utf-8")

    replace_from_file(first)
    _, backup = replace_from_file(second)

    assert backup is not None
    assert backup.exists()
    assert json.loads(target.read_text(encoding="utf-8"))[0]["title"] == "new"


def test_load_entries_indexes_by_bgm_id(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"items": [{"bgm_id": 285757, "title": "OPM"}]}), encoding="utf-8")
    assert load_entries(path)[285757]["title"] == "OPM"
