import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COLLECTION_HELPERS = ROOT / "includes" / "collection.php"


def php_json(expression: str):
    if shutil.which("php") is None:
        pytest.skip("PHP CLI is not installed")

    source = (
        f"require {json.dumps(str(COLLECTION_HELPERS))}; "
        f"echo json_encode({expression}, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);"
    )
    result = subprocess.run(
        ["php", "-r", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_collection_filters_are_normalized_and_sort_is_whitelisted():
    filters = php_json(
        "normalize_collection_filters(["
        "'q' => '  Chobits  ', "
        "'year' => 'not-a-year', "
        "'rating_min' => '8', "
        "'progress' => 'invalid', "
        "'sort' => 'c.subject_id DESC; DROP TABLE collections'"
        "])"
    )

    assert filters["q"] == "Chobits"
    assert filters["year"] == ""
    assert filters["rating_min"] == 8
    assert filters["progress"] == "all"
    assert filters["sort"] == "collected_desc"


def test_keyword_search_covers_names_and_infobox_aliases():
    parts = php_json(
        "collection_query_parts(['q' => 'Chobits', 'sort' => 'rating_desc'])"
    )

    assert "s.name LIKE :keyword_name" in parts["where"]
    assert "s.name_cn LIKE :keyword_name_cn" in parts["where"]
    assert "s.infobox LIKE :keyword_infobox" in parts["where"]
    assert parts["params"]["keyword_name"] == "%Chobits%"
    assert parts["params"]["keyword_name_cn"] == "%Chobits%"
    assert parts["params"]["keyword_infobox"] == "%Chobits%"
    assert "c.my_rating DESC" in parts["order_by"]


def test_like_wildcards_are_treated_as_literal_characters():
    parts = php_json("collection_query_parts(['q' => '100%_test'])")
    assert parts["params"]["keyword_name"] == r"%100\%\_test%"


def test_collection_url_keeps_filters_during_pagination():
    url = php_json(
        "collection_url(["
        "'q' => 'Mahou Shoujo', "
        "'year' => '2011', "
        "'media_type' => 'BD', "
        "'rating_min' => 9, "
        "'progress' => 'filled', "
        "'sort' => 'year_desc'"
        "], 3)"
    )

    assert url.startswith("collection.php?")
    assert "q=Mahou%20Shoujo" in url
    assert "year=2011" in url
    assert "media_type=BD" in url
    assert "rating_min=9" in url
    assert "progress=filled" in url
    assert "sort=year_desc" in url
    assert "page=3" in url


def test_collection_queries_start_from_the_small_personal_collection_set():
    source = COLLECTION_HELPERS.read_text(encoding="utf-8")
    assert "FROM collections c FORCE INDEX (idx_collections_collected)" in source
    assert "STRAIGHT_JOIN " in source
    assert ".subjects s FORCE INDEX (PRIMARY)" in source
