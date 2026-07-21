import json
from pathlib import Path

from importer.import_archive_dump import import_dump


def write_jsonlines(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_archive_dump_dry_run_reads_subject_episode_and_relations(tmp_path):
    write_jsonlines(tmp_path / "subject.jsonlines", [{"id": 1, "type": 2, "name": "Subject"}])
    write_jsonlines(tmp_path / "episode.jsonlines", [{"id": 10, "subject_id": 1, "sort": 1}])
    write_jsonlines(tmp_path / "subject-relations.jsonlines", [{"subject_id": 1, "related_subject_id": 2, "relation": "续集"}])
    write_jsonlines(tmp_path / "subject-persons.jsonlines", [{"subject_id": 1, "person_id": 3, "relation": "导演"}])
    write_jsonlines(tmp_path / "person-characters.jsonlines", [{"person_id": 3, "character_id": 4, "subject_id": 1}])

    totals = import_dump(tmp_path, dry_run=True)

    assert totals["subjects"] == (1, 0)
    assert totals["episodes"] == (1, 0)
    assert totals["subject_relations"] == (1, 0)
    assert totals["subject_persons"] == (1, 0)
    assert totals["person_characters"] == (1, 0)


def test_subject_persons_appear_eps_is_normalized_for_json_column():
    from importer.import_archive_dump import normalize_appear_eps, normalize_row

    assert normalize_appear_eps("") is None
    assert normalize_appear_eps("9,25") == [9, 25]
    assert normalize_appear_eps("1,2,3") == [1, 2, 3]
    assert normalize_appear_eps([1, 2, 3]) == [1, 2, 3]
    assert normalize_row({"subject_id": 1, "person_id": 2, "appear_eps": "1,2,3"})["appear_eps"] == "[1, 2, 3]"
    assert normalize_row({"subject_id": 1, "person_id": 2, "appear_eps": ""})["appear_eps"] is None


def test_importer_does_not_depend_on_fastapi_app_database():
    source = Path("importer/import_archive_dump.py").read_text(encoding="utf-8")
    assert "from app.database" not in source
    assert "from app.schema_utils" not in source
    assert "tools.php_config_reader" in source


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def executemany(self, sql, batch):
        self.conn.executed.append((sql, list(batch)))


class _FakeConnection:
    def __init__(self):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def cursor(self):
        return _FakeCursor(self)
    def commit(self):
        self.commits += 1
    def rollback(self):
        self.rollbacks += 1


def test_archive_import_batches_upserts_and_commits(tmp_path, monkeypatch, capsys):
    from importer import import_archive_dump as importer

    write_jsonlines(tmp_path / "subject.jsonlines", [
        {"id": 1, "type": 2, "name": "A"},
        {"id": 2, "type": 2, "name": "B"},
        {"id": 3, "type": 2, "name": "C"},
    ])
    conn = _FakeConnection()
    monkeypatch.setattr(importer, "get_table_columns", lambda table: {"id", "type", "name"})
    monkeypatch.setattr(importer, "connect_public_database", lambda: conn)

    assert importer.import_jsonlines_file(tmp_path / "subject.jsonlines", "subjects", batch_size=2) == (3, 0)

    assert len(conn.executed) == 2
    assert [len(batch) for _, batch in conn.executed] == [2, 1]
    assert conn.commits == 2
    assert conn.rollbacks == 0
    assert "ON DUPLICATE KEY UPDATE" in conn.executed[0][0]
    assert "subjects: committed batch=2 total=2" in capsys.readouterr().out


def test_archive_import_limit_is_checked_before_batching(tmp_path, monkeypatch):
    from importer import import_archive_dump as importer

    write_jsonlines(tmp_path / "subject.jsonlines", [
        {"id": 1, "type": 2, "name": "A"},
        {"id": 2, "type": 2, "name": "B"},
        {"id": 3, "type": 2, "name": "C"},
    ])
    conn = _FakeConnection()
    monkeypatch.setattr(importer, "get_table_columns", lambda table: {"id", "type", "name"})
    monkeypatch.setattr(importer, "connect_public_database", lambda: conn)

    assert importer.import_jsonlines_file(tmp_path / "subject.jsonlines", "subjects", limit=2, batch_size=1000) == (2, 0)
    assert [len(batch) for _, batch in conn.executed] == [2]
