from pathlib import Path
import re

from importer.import_archive_dump import ARCHIVE_FILES


EXPECTED_TABLES = {
    "subjects": {"id", "type", "name", "name_cn", "infobox", "platform", "summary", "tags", "meta_tags", "score", "score_details", "rank", "favorite", "date", "nsfw", "series"},
    "episodes": {"id", "name", "name_cn", "description", "airdate", "disc", "duration", "subject_id", "sort", "type"},
    "persons": {"id", "name", "type", "career", "infobox", "summary", "comments", "collects"},
    "characters": {"id", "role", "name", "infobox", "summary", "comments", "collects"},
    "subject_persons": {"subject_id", "person_id", "position", "appear_eps"},
    "subject_characters": {"subject_id", "character_id", "type", "order"},
    "subject_relations": {"subject_id", "relation_type", "related_subject_id", "order"},
    "person_characters": {"subject_id", "person_id", "character_id", "summary"},
    "person_relations": {"person_type", "person_id", "related_person_id", "relation_type", "spoiler", "ended"},
}


def _columns_for(table: str) -> set[str]:
    sql = Path("sql/create_chrono_bangumi_tables.sql").read_text()
    match = re.search(rf"CREATE TABLE IF NOT EXISTS `{table}` \((.*?)\n\) ENGINE", sql, re.S)
    assert match, f"missing table {table}"
    return set(re.findall(r"^\s+`([^`]+)`", match.group(1), re.M))


def test_archive_importer_tables_have_sql_columns():
    assert set(ARCHIVE_FILES) == set(EXPECTED_TABLES)
    for table, columns in EXPECTED_TABLES.items():
        assert columns <= _columns_for(table)



def test_collections_table_does_not_store_public_bangumi_fields():
    sql = Path("sql/create_chrono_library_tables.sql").read_text()
    match = re.search(r"CREATE TABLE IF NOT EXISTS `collections` \((.*?)\n\) ENGINE", sql, re.S)
    assert match, "missing collections table"
    collection_columns = set(re.findall(r"^\s+`([^`]+)`", match.group(1), re.M))
    assert {"name", "name_cn", "summary", "tags", "image", "infobox"}.isdisjoint(collection_columns)


def test_table_sql_does_not_create_or_select_databases():
    for path in (Path("sql/create_chrono_bangumi_tables.sql"), Path("sql/create_chrono_library_tables.sql")):
        sql = path.read_text().upper()
        assert "CREATE DATABASE `" not in sql
        assert "USE `" not in sql


def test_archive_small_unsigned_types_are_preserved():
    sql = Path("sql/create_chrono_bangumi_tables.sql").read_text()
    assert "`type` TINYINT UNSIGNED" in sql
    assert "`platform` SMALLINT UNSIGNED" in sql
    assert "`role` TINYINT UNSIGNED" in sql
    assert "`disc` SMALLINT UNSIGNED" in sql
    assert "`order` SMALLINT UNSIGNED" in sql
    assert "`position` SMALLINT UNSIGNED" in sql
    assert "`relation_type` SMALLINT UNSIGNED" in sql
    assert "`comments` INT UNSIGNED" in sql
    assert "`collects` INT UNSIGNED" in sql


def test_required_query_indexes_exist():
    sql = Path("sql/create_indexes.sql").read_text()
    assert "`idx_subjects_type_name_name_cn`" in sql
    assert "ON `subjects` (`type`, `name`, `name_cn`)" in sql
    assert "`idx_episodes_subject_id`" in sql
    assert "`idx_subject_relations_subject_related`" in sql
    assert "`idx_person_characters_subject_character`" in sql
    assert "`idx_person_relations_person_related`" in sql
