from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANGUMI = (ROOT / "includes" / "bangumi.php").read_text(encoding="utf-8")
INDEX_SQL = (ROOT / "sql" / "create_chrono_bangumi_indexes.sql").read_text(encoding="utf-8")
SCHEMA_SQL = (ROOT / "database" / "chrono_bangumi_schema.sql").read_text(encoding="utf-8")
MIGRATION_SQL = (ROOT / "sql" / "migrations" / "004_add_subjects_pagination_indexes.sql").read_text(encoding="utf-8")


def test_list_anime_uses_indexed_inner_pagination_for_type_2():
    assert "FROM (" in BANGUMI
    assert "SELECT id, date" in BANGUMI
    assert "FROM subjects FORCE INDEX (idx_subjects_type_date_id)" in BANGUMI
    assert "WHERE type = 2" in BANGUMI
    assert "ORDER BY date DESC, id DESC" in BANGUMI
    assert "LIMIT ' . $limit . ' OFFSET ' . $offset" in BANGUMI


def test_list_anime_reads_full_fields_only_after_page_ids():
    select_inner = BANGUMI.index("SELECT id, date")
    join_full = BANGUMI.index("JOIN subjects s FORCE INDEX (PRIMARY)")
    assert select_inner < join_full
    assert "s.id" in BANGUMI
    assert "s.name" in BANGUMI
    assert "s.name_cn" in BANGUMI
    assert "s.date" in BANGUMI
    assert "s.score" in BANGUMI
    assert "s.favorite" not in BANGUMI[BANGUMI.index("function list_anime"):BANGUMI.index("function count_anime")]
    assert "meta_tags" not in BANGUMI[BANGUMI.index("function list_anime"):BANGUMI.index("function count_anime")]


def test_list_anime_sanitizes_limit_offset_before_sql_interpolation():
    assert "$limit = max(1, min(200, (int) $limit));" in BANGUMI
    assert "$offset = max(0, (int) $offset);" in BANGUMI
    assert "bindValue(':limit'" not in BANGUMI[BANGUMI.index("function list_anime"):BANGUMI.index("function count_anime")]


def test_list_anime_joins_cover_and_collection_by_primary_key_after_pagination():
    assert "cover_cache cc FORCE INDEX (PRIMARY)" in BANGUMI
    assert "cc.subject_id = p.id AND cc.status = \\'cached\\'" in BANGUMI
    assert "collections c FORCE INDEX (PRIMARY)" in BANGUMI
    assert "c.subject_id = p.id AND c.collected = TRUE" in BANGUMI
    assert "cc.local_path AS cover_local_path" in BANGUMI
    assert "c.subject_id AS collected_subject_id" in BANGUMI


def test_count_anime_still_counts_type_2_only():
    assert "SELECT COUNT(*) FROM subjects WHERE type = 2" in BANGUMI


def test_pagination_indexes_exist_in_schema_index_file_and_migration():
    for sql in [INDEX_SQL, SCHEMA_SQL, MIGRATION_SQL]:
        assert "idx_subjects_type_date_id" in sql
        assert "ON `subjects` (`type`, `date`, `id`)" in sql
        assert "idx_subjects_type_score_id" in sql
        assert "ON `subjects` (`type`, `score`, `id`)" in sql


def test_future_filter_guidance_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "筛选条件必须进入内层分页查询" in readme
    assert "count_anime() 使用相同条件" in readme
    assert "meta_tags" in readme
    assert "subject_meta_tags" in readme
