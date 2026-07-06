from importer.infobox_parser import parse_infobox


def test_multiline_alias_parse():
    raw = """{{Infobox animanga/TVAnime
|中文名= 一拳超人 第三季
|别名={
[One Punch Man 3]
[One-Punch Man Season 3]
}
|话数= 12
|放送开始= 2025年10月12日
|放送星期= 星期日
}}"""
    assert parse_infobox(raw) == [
        {"key": "中文名", "value": "一拳超人 第三季"},
        {"key": "别名", "value": [{"v": "One Punch Man 3"}, {"v": "One-Punch Man Season 3"}]},
        {"key": "话数", "value": "12"},
        {"key": "放送开始", "value": "2025年10月12日"},
        {"key": "放送星期", "value": "星期日"},
    ]


def test_empty_infobox_is_safe():
    assert parse_infobox("") == []
    assert parse_infobox(None) == []
