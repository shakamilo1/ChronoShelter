from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_API = "https://api.bgm.tv/v0/subjects/{subject_id}/image?type=large"


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


def local_cover_path(subject_id: int) -> str | None:
    path = PROJECT_ROOT / "media" / "covers" / f"{subject_id}.jpg"
    return f"media/covers/{subject_id}.jpg" if path.exists() and path.stat().st_size > 0 else None


def api_cover_url(subject_id: int) -> str:
    return IMAGE_API.format(subject_id=subject_id)


def normalize_subject_row(row: dict) -> dict:
    row = dict(row)
    subject_id = int(row["id"])
    row["name_jp"] = pick(row, "name", "name_jp")
    row["rating_score"] = pick(row, "score", "rating_score")
    row["tags"] = loads(pick(row, "tags", "tags_json", default=[]), [])
    row["meta_tags"] = loads(pick(row, "meta", "meta_tags", "meta_tags_json", default=[]), [])
    row["infobox"] = loads(pick(row, "infobox", "infobox_json", default=[]), [])
    row["cover_local_path"] = local_cover_path(subject_id)
    row["image_large"] = api_cover_url(subject_id)
    row["image_small"] = api_cover_url(subject_id)
    row.setdefault("air_date", pick(row, "date"))
    row.setdefault("air_year", row["air_date"].year if hasattr(row.get("air_date"), "year") else None)
    row.setdefault("air_month", row["air_date"].month if hasattr(row.get("air_date"), "month") else None)
    return row
