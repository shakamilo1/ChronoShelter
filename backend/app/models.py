from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

@dataclass
class Anime:
    id: int
    name_jp: str | None
    name_cn: str | None
    name_en: str | None
    type: str | None
    platform: int | None
    air_date: date | None
    air_year: int | None
    air_month: int | None
    air_weekday: str | None
    raw_air_date: str | None
    eps: int | None
    summary: str | None
    rating_score: float | None
    rating_count: int | None
    rank: int | None
    image_small: str | None
    image_large: str | None
    tags_json: Any
    meta_tags_json: Any
    infobox_json: Any
    raw_infobox: str | None
    nsfw: bool
    created_at: datetime | None
    updated_at: datetime | None
