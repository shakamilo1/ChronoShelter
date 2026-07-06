from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from importer.infobox_parser import parse_infobox
from importer.normalizer import (
    choose_name_en,
    infobox_value,
    normalize_air_date,
    normalize_eps,
    normalize_tags,
    rating_count_from_score_details,
)


@dataclass
class UnifiedAnimeModel:
    id: int
    name_jp: str | None = None
    name_cn: str | None = None
    name_en: str | None = None
    air_date: date | None = None
    air_year: int | None = None
    air_month: int | None = None
    raw_air_date: str | None = None
    broadcast: str | None = None
    air_weekday: str | None = None
    eps: int | None = None
    summary: str | None = None
    rating_score: float | None = None
    rating_count: int | None = None
    rank: int | None = None
    tags: list[dict[str, Any]] | None = None
    meta_tags: list[str] | None = None
    infobox: list[dict[str, Any]] | None = None
    raw_infobox: str | None = None
    image_small: str | None = None
    image_large: str | None = None
    cover_local_path: str | None = None
    nsfw: bool = False
    type: str | None = None
    platform: int | None = None


def _first_present(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _bangumi_data_air_date(entry: dict | None):
    if not entry:
        return None, None, None, None
    begin = entry.get("begin") or entry.get("air_date") or entry.get("date")
    if isinstance(begin, str) and begin:
        parts = begin.split("T", 1)[0].split(" ", 1)[0]
        if len(parts) == 10 and parts[4] == "-":
            y, m, d = map(int, parts.split("-"))
            return date(y, m, d), y, m, begin
        return normalize_air_date(begin)
    return None, None, None, None


def _bangumi_data_broadcast(entry: dict | None) -> str | None:
    if not entry:
        return None
    broadcast = entry.get("broadcast")
    if isinstance(broadcast, str):
        return broadcast or None
    if isinstance(broadcast, dict):
        return _first_present(broadcast.get("raw"), broadcast.get("rrule"), broadcast.get("time"))
    return None


def merge_subjects(api_subject: dict | None, bangumi_data_entry: dict | None = None) -> UnifiedAnimeModel:
    api_subject = api_subject or {}
    entry = bangumi_data_entry or {}
    subject_id = int(_first_present(api_subject.get("id"), entry.get("bgm_id"), entry.get("id")))

    infobox = parse_infobox(api_subject.get("infobox"))
    api_air_raw = api_subject.get("date") or infobox_value(infobox, "放送开始")
    api_air_date, api_air_year, api_air_month, api_raw_air_date = normalize_air_date(api_air_raw)
    bd_air_date, bd_air_year, bd_air_month, bd_raw_air_date = _bangumi_data_air_date(entry)

    rating = api_subject.get("rating") or {}
    images = api_subject.get("images") or {}
    title_translate = entry.get("titleTranslate") or {}
    cn_titles = title_translate.get("zh-Hans") or title_translate.get("zh-CN") or []
    en_titles = title_translate.get("en") or []
    name_cn = _first_present(api_subject.get("name_cn"), cn_titles[0] if cn_titles else None)
    name_en = _first_present(choose_name_en(infobox), en_titles[0] if en_titles else None)

    return UnifiedAnimeModel(
        id=subject_id,
        name_jp=_first_present(api_subject.get("name"), entry.get("title")),
        name_cn=name_cn,
        name_en=name_en,
        air_date=_first_present(bd_air_date, api_air_date),
        air_year=_first_present(bd_air_year, api_air_year),
        air_month=_first_present(bd_air_month, api_air_month),
        raw_air_date=_first_present(bd_raw_air_date, api_raw_air_date),
        broadcast=_bangumi_data_broadcast(entry),
        air_weekday=infobox_value(infobox, "放送星期"),
        eps=normalize_eps(api_subject.get("eps") or infobox_value(infobox, "话数") or entry.get("eps")),
        summary=api_subject.get("summary") or None,
        rating_score=rating.get("score") or None,
        rating_count=rating_count_from_score_details(rating.get("score_details")),
        rank=api_subject.get("rank"),
        tags=normalize_tags(api_subject.get("tags")),
        meta_tags=api_subject.get("meta_tags") or [],
        infobox=infobox,
        raw_infobox=api_subject.get("infobox") or None,
        image_small=images.get("small"),
        image_large=images.get("large") or images.get("common"),
        nsfw=bool(api_subject.get("nsfw", False)),
        type=str(api_subject.get("type")) if api_subject.get("type") is not None else None,
        platform=api_subject.get("platform"),
    )
