import json

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
