from datetime import date

from importer.merge_engine import merge_subjects


def test_bangumi_data_time_wins_and_api_content_kept():
    api = {
        "id": 285757,
        "type": 2,
        "name": "ワンパンマン 第3期",
        "name_cn": "一拳超人 第三季",
        "date": "2025年10月",
        "infobox": "|别名={\n[One Punch Man 3]\n}\n|话数= 12",
        "tags": [{"name": "战斗", "count": 10}],
        "summary": "summary",
    }
    bd = {"bgm_id": 285757, "title": "ワンパンマン", "begin": "2025-10-12T23:45:00+09:00", "broadcast": "R/2025-10-12T23:45:00+09:00/P7D"}
    unified = merge_subjects(api, bd)
    assert unified.air_date == date(2025, 10, 12)
    assert unified.broadcast.startswith("R/2025")
    assert unified.summary == "summary"
    assert unified.tags == [{"name": "战斗", "count": 10}]
