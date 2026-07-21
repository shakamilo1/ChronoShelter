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
    sql = Path("sql/create_chrono_bangumi_tables.sql").read_text(encoding="utf-8")
    match = re.search(rf"CREATE TABLE IF NOT EXISTS `{table}` \((.*?)\n\) ENGINE", sql, re.S)
    assert match, f"missing table {table}"
    return set(re.findall(r"^\s+`([^`]+)`", match.group(1), re.M))


def test_archive_importer_tables_have_sql_columns():
    assert set(ARCHIVE_FILES) == set(EXPECTED_TABLES)
    for table, columns in EXPECTED_TABLES.items():
        assert columns <= _columns_for(table)



def test_collections_table_does_not_store_public_bangumi_fields():
    sql = Path("sql/create_chrono_library_tables.sql").read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE IF NOT EXISTS `collections` \((.*?)\n\) ENGINE", sql, re.S)
    assert match, "missing collections table"
    collection_columns = set(re.findall(r"^\s+`([^`]+)`", match.group(1), re.M))
    assert {"name", "name_cn", "summary", "tags", "image", "infobox"}.isdisjoint(collection_columns)


def test_table_sql_does_not_create_or_select_databases():
    for path in (Path("sql/create_chrono_bangumi_tables.sql"), Path("sql/create_chrono_library_tables.sql")):
        sql = path.read_text(encoding="utf-8").upper()
        assert "CREATE DATABASE `" not in sql
        assert "USE `" not in sql


def test_archive_small_unsigned_types_are_preserved():
    sql = Path("sql/create_chrono_bangumi_tables.sql").read_text(encoding="utf-8")
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
    sql = Path("sql/create_chrono_bangumi_indexes.sql").read_text(encoding="utf-8")
    assert "`idx_subjects_type_name_name_cn`" in sql
    assert "ON `subjects` (`type`, `name`(191), `name_cn`(191))" in sql
    assert "`idx_episodes_subject_id`" in sql
    assert "`idx_subject_relations_subject_related`" in sql
    assert "`idx_person_characters_subject_character`" in sql
    assert "`idx_person_relations_person_related`" in sql
    library_sql = Path("sql/create_chrono_library_indexes.sql").read_text(encoding="utf-8")
    assert "`idx_collections_collected`" in library_sql
    assert "`idx_cover_cache_status`" in library_sql


def test_subject_name_index_fits_mariadb_utf8mb4_key_limit():
    """The subject search index must be creatable on InnoDB with utf8mb4.

    InnoDB's common maximum index key length is 3072 bytes. `type` is a
    TINYINT (1 byte) and the two VARCHAR prefixes use up to 4 bytes per
    utf8mb4 character, so 1 + 191*4 + 191*4 = 1529 bytes.
    """
    sql = Path("sql/create_chrono_bangumi_indexes.sql").read_text(encoding="utf-8")
    full_index = "ON `subjects` (`type`, `name`, `name_cn`)"
    prefix_index = "ON `subjects` (`type`, `name`(191), `name_cn`(191))"

    assert full_index not in sql
    assert prefix_index in sql
    assert 1 + (191 * 4) + (191 * 4) <= 3072


def test_split_index_files_target_single_databases():
    bangumi_sql = Path("sql/create_chrono_bangumi_indexes.sql").read_text(encoding="utf-8")
    library_sql = Path("sql/create_chrono_library_indexes.sql").read_text(encoding="utf-8")

    assert "Run after selecting" not in bangumi_sql
    assert "Run after selecting" not in library_sql
    assert "collections" not in bangumi_sql
    assert "cover_cache" not in bangumi_sql
    assert "subjects" not in library_sql
    assert "episodes" not in library_sql
