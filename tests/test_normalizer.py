import json
from datetime import date

from importer.import_subject_jsonlines import import_file
from importer.normalizer import choose_name_en, normalize_air_date, normalize_eps


def test_eps_12():
    assert normalize_eps("12") == 12


def test_eps_star():
    assert normalize_eps("*") is None


def test_full_air_date():
    assert normalize_air_date("2025年10月12日") == (date(2025, 10, 12), 2025, 10, "2025年10月12日")


def test_year_only_air_date():
    air_date, year, month, raw = normalize_air_date("2027年")
    assert air_date is None
    assert year == 2027
    assert month is None
    assert raw == "2027年"


def test_name_en_not_tv():
    infobox = [{"key": "别名", "value": [{"v": "TV"}, {"v": "One Punch Man 3"}]}]
    assert choose_name_en(infobox) == "One Punch Man 3"


def test_dry_run_does_not_write_database(tmp_path):
    data = {
        "id": 285757,
        "type": 2,
        "name": "ワンパンマン 第3期",
        "name_cn": "一拳超人 第三季",
        "infobox": "|话数= 12",
        "rating": {"score": 0, "score_details": {"1": 0}},
    }
    path = tmp_path / "subject.jsonlines"
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    assert import_file(path, dry_run=True) == (1, 0, 0)
