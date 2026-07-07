from __future__ import annotations

import json
from typing import Any


def loads(value: Any, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def pick(row: dict, *names, default=None):
    for name in names:
        if name in row and row.get(name) is not None:
            return row.get(name)
    return default


def image_url(subject: dict, size: str = "large") -> str | None:
    images = loads(pick(subject, "images", "image", default={}), {})
    if isinstance(images, dict):
        return images.get(size) or images.get("common") or images.get("medium") or images.get("small")
    return None


def normalize_subject_row(row: dict) -> dict:
    row = dict(row)
    row["name_jp"] = pick(row, "name", "name_jp")
    row["rating_score"] = pick(row, "score", "rating_score")
    row["tags"] = loads(pick(row, "tags", "tags_json", default=[]), [])
    row["meta_tags"] = loads(pick(row, "meta", "meta_tags", "meta_tags_json", default=[]), [])
    row["infobox"] = loads(pick(row, "infobox", "infobox_json", default=[]), [])
    row["image_large"] = image_url(row, "large")
    row["image_small"] = image_url(row, "small")
    row.setdefault("cover_local_path", None)
    row.setdefault("air_date", pick(row, "date"))
    row.setdefault("air_year", row["air_date"].year if hasattr(row.get("air_date"), "year") else None)
    row.setdefault("air_month", row["air_date"].month if hasattr(row.get("air_date"), "month") else None)
    return row
