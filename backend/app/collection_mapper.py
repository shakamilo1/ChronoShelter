from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ID_FIELDS = ("bangumi_id", "anime_id", "subject_id")
COLLECTED_FIELDS = ("collected", "is_collected")
DATE_FIELDS = ("collection_date", "collect_date", "created_at", "date")
MEDIA_FIELDS = ("media_type", "medium", "media")
SUBTITLE_FIELDS = ("subtitle_group", "subgroup", "fansub")
SOURCE_FIELDS = ("source_site", "source", "site")
RATING_FIELDS = ("my_rating", "rating")
NOTES_FIELDS = ("notes", "note", "remark")
EXTRA_FIELDS = ("extra_json", "extra", "other")


@dataclass(frozen=True)
class CollectionFieldMap:
    id_field: str | None
    collected: str | None
    collection_date: str | None
    media_type: str | None
    subtitle_group: str | None
    source_site: str | None
    my_rating: str | None
    notes: str | None
    extra: str | None


def _pick(columns: set[str], names: tuple[str, ...]) -> str | None:
    return next((name for name in names if name in columns), None)


def build_collection_field_map(columns: set[str]) -> CollectionFieldMap:
    return CollectionFieldMap(
        id_field=_pick(columns, ID_FIELDS),
        collected=_pick(columns, COLLECTED_FIELDS),
        collection_date=_pick(columns, DATE_FIELDS),
        media_type=_pick(columns, MEDIA_FIELDS),
        subtitle_group=_pick(columns, SUBTITLE_FIELDS),
        source_site=_pick(columns, SOURCE_FIELDS),
        my_rating=_pick(columns, RATING_FIELDS),
        notes=_pick(columns, NOTES_FIELDS),
        extra=_pick(columns, EXTRA_FIELDS),
    )


def normalize_collection_row(row: dict[str, Any] | None, fmap: CollectionFieldMap) -> dict[str, Any]:
    row = row or {}
    return {
        "collection_id_value": row.get(fmap.id_field) if fmap.id_field else None,
        "collected": bool(row.get(fmap.collected)) if fmap.collected and row.get(fmap.collected) is not None else False,
        "collection_date": row.get(fmap.collection_date) if fmap.collection_date else None,
        "media_type": row.get(fmap.media_type) if fmap.media_type else None,
        "subtitle_group": row.get(fmap.subtitle_group) if fmap.subtitle_group else None,
        "source_site": row.get(fmap.source_site) if fmap.source_site else None,
        "my_rating": row.get(fmap.my_rating) if fmap.my_rating else None,
        "notes": row.get(fmap.notes) if fmap.notes else None,
        "extra_json": row.get(fmap.extra) if fmap.extra else None,
    }
