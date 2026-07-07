from __future__ import annotations

import re
from datetime import date

BAD_EN = {"tv", "ova", "oad", "日本", "漫画改", "战斗", "動畫", "动画", "剧场版"}
PREFERRED_EN_RE = re.compile(r"\b(season|tv|movie|ova|one punch man)\b", re.I)


def normalize_eps(value):
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "*", "未定", "?", "？"}:
        return None
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def normalize_air_date(value):
    if value is None:
        return None, None, None, None
    text = str(value).strip()
    if text in {"", "未定", "?", "？", "*"}:
        return None, None, None, None
    full = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if full:
        y, m, d = map(int, full.groups())
        return date(y, m, d), y, m, text
    ym = re.fullmatch(r"(\d{4})年(\d{1,2})月", text)
    if ym:
        y, m = map(int, ym.groups())
        return None, y, m, text
    y = re.fullmatch(r"(\d{4})年", text)
    if y:
        return None, int(y.group(1)), None, text
    return None, None, None, text


def infobox_value(infobox, key):
    for item in infobox or []:
        if item.get("key") == key:
            return item.get("value")
    return None


def choose_name_en(infobox, existing=None):
    candidates = []
    aliases = infobox_value(infobox, "别名")
    if isinstance(aliases, list):
        candidates.extend(str(x.get("v", "")).strip() for x in aliases)
    if existing:
        candidates.append(str(existing).strip())

    valid = []
    for candidate in candidates:
        lowered = candidate.lower()
        if not candidate or lowered in BAD_EN:
            continue
        if not candidate.isascii() or not re.search(r"[A-Za-z]", candidate):
            continue
        if len(candidate) <= 3 and lowered in {"tv", "ova"}:
            continue
        valid.append(candidate)
    if not valid:
        return None
    preferred = [v for v in valid if PREFERRED_EN_RE.search(v)]
    return (preferred or valid)[0]


def rating_count_from_score_details(score_details):
    if not isinstance(score_details, dict):
        return None
    total = 0
    for value in score_details.values():
        try:
            total += int(value)
        except (TypeError, ValueError):
            pass
    return total


def normalize_tags(tags):
    if not isinstance(tags, list):
        return []
    return [{"name": t.get("name"), "count": t.get("count", 0)} for t in tags if t.get("name")]
