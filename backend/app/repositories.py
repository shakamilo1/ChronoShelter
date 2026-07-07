import json
from .collection_mapper import build_collection_field_map, normalize_collection_row
from .database import get_connection
from .schema_utils import get_table_columns, table_exists


def _loads(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _first_existing(row, *names):
    for name in names:
        if name in row and row.get(name) is not None:
            return row.get(name)
    return None


def _hydrate_anime(row):
    if not row:
        return None
    row = dict(row)
    row["tags"] = _loads(_first_existing(row, "tags_json", "tags"), [])
    row["meta_tags"] = _loads(_first_existing(row, "meta_tags_json", "meta_tags"), [])
    row["infobox"] = _loads(_first_existing(row, "infobox_json", "infobox"), [])
    row["sites"] = _loads(_first_existing(row, "sites_json"), [])
    row.setdefault("raw_infobox", _first_existing(row, "raw_infobox", "infobox"))
    row.setdefault("cover_local_path", None)
    row.setdefault("cover_cache_status", None)
    row.setdefault("cover_cached_at", None)
    return row


def _collection_field_map():
    return build_collection_field_map(get_table_columns("my_collection"))


def _fetch_collections(anime_ids):
    if not anime_ids or not table_exists("my_collection"):
        return {}
    fmap = _collection_field_map()
    if not fmap.id_field:
        return {}
    placeholders = ",".join(["%s"] * len(anime_ids))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM my_collection WHERE `{fmap.id_field}` IN ({placeholders})", anime_ids)
        rows = cur.fetchall()
    return {int(row[fmap.id_field]): normalize_collection_row(row, fmap) for row in rows if row.get(fmap.id_field) is not None}


def _merge_collection(anime_row, collection_map):
    anime_id = int(anime_row["id"])
    merged = _hydrate_anime(anime_row)
    merged.update(collection_map.get(anime_id, normalize_collection_row(None, _collection_field_map())))
    return merged


def list_anime(q: str | None = None, limit: int = 40, offset: int = 0):
    sql = "SELECT * FROM bangumi_anime"
    params = []
    cols = get_table_columns("bangumi_anime")
    if q:
        clauses = []
        for col in ("name_cn", "name_jp", "name_en"):
            if col in cols:
                clauses.append(f"`{col}` LIKE %s")
                params.append(f"%{q}%")
        if clauses:
            sql += " WHERE " + " OR ".join(clauses)
    if {"air_date", "air_year", "air_month"}.issubset(cols):
        sql += " ORDER BY COALESCE(air_date, STR_TO_DATE(CONCAT(air_year,'-',COALESCE(air_month,1),'-01'), '%Y-%m-%d')) DESC, id DESC LIMIT %s OFFSET %s"
    else:
        sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    collections = _fetch_collections([int(row["id"]) for row in rows])
    return [_merge_collection(row, collections) for row in rows]


def get_anime(anime_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM bangumi_anime WHERE id=%s", (anime_id,))
        row = cur.fetchone()
    if not row:
        return None
    return _merge_collection(row, _fetch_collections([anime_id]))


def one_click_collect(anime_id: int):
    if not table_exists("my_collection"):
        raise RuntimeError("my_collection table does not exist. Run schema inspection and a safe migration first.")
    fmap = _collection_field_map()
    if not fmap.id_field:
        raise RuntimeError("my_collection needs a bangumi_id/anime_id/subject_id column for collection mapping.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM my_collection WHERE `{fmap.id_field}`=%s LIMIT 1", (anime_id,))
        existing = cur.fetchone()
        assignments = []
        params = []
        if fmap.collected:
            assignments.append(f"`{fmap.collected}`=%s")
            params.append(True)
        if fmap.collection_date and fmap.collection_date not in {"created_at"}:
            assignments.append(f"`{fmap.collection_date}`=COALESCE(`{fmap.collection_date}`, CURDATE())")
        if existing:
            if assignments:
                params.append(anime_id)
                cur.execute(f"UPDATE my_collection SET {', '.join(assignments)} WHERE `{fmap.id_field}`=%s", params)
            return
        columns = [fmap.id_field]
        values = [anime_id]
        if fmap.collected:
            columns.append(fmap.collected)
            values.append(True)
        if fmap.collection_date and fmap.collection_date not in {"created_at"}:
            columns.append(fmap.collection_date)
            values.append(None)
        placeholders = ",".join(["%s"] * len(columns))
        quoted = ",".join(f"`{col}`" for col in columns)
        cur.execute(f"INSERT INTO my_collection ({quoted}) VALUES ({placeholders})", values)
        if fmap.collection_date and fmap.collection_date not in {"created_at"}:
            cur.execute(f"UPDATE my_collection SET `{fmap.collection_date}`=CURDATE() WHERE `{fmap.id_field}`=%s AND `{fmap.collection_date}` IS NULL", (anime_id,))


def save_collection(anime_id: int, form: dict):
    if not table_exists("my_collection"):
        raise RuntimeError("my_collection table does not exist. Run schema inspection and a safe migration first.")
    fmap = _collection_field_map()
    if not fmap.id_field:
        raise RuntimeError("my_collection needs a bangumi_id/anime_id/subject_id column for collection mapping.")
    values_by_logical = {
        "collected": form.get("collected") in {"on", "true", "1", "yes"},
        "collection_date": form.get("collection_date") or None,
        "media_type": form.get("media_type") or None,
        "subtitle_group": form.get("subtitle_group") or None,
        "source_site": form.get("source_site") or None,
        "my_rating": float(form["my_rating"]) if form.get("my_rating") not in (None, "") else None,
        "notes": form.get("notes") or None,
        "extra": json.dumps({"other": form.get("extra")}, ensure_ascii=False) if form.get("extra") else None,
    }
    logical_to_column = {
        "collected": fmap.collected,
        "collection_date": fmap.collection_date if fmap.collection_date not in {"created_at"} else None,
        "media_type": fmap.media_type,
        "subtitle_group": fmap.subtitle_group,
        "source_site": fmap.source_site,
        "my_rating": fmap.my_rating,
        "notes": fmap.notes,
        "extra": fmap.extra,
    }
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM my_collection WHERE `{fmap.id_field}`=%s LIMIT 1", (anime_id,))
        existing = cur.fetchone()
        if existing:
            assignments = []
            params = []
            for logical, col in logical_to_column.items():
                if col:
                    assignments.append(f"`{col}`=%s")
                    params.append(values_by_logical[logical])
            if assignments:
                params.append(anime_id)
                cur.execute(f"UPDATE my_collection SET {', '.join(assignments)} WHERE `{fmap.id_field}`=%s", params)
            return
        columns = [fmap.id_field]
        values = [anime_id]
        for logical, col in logical_to_column.items():
            if col:
                columns.append(col)
                values.append(values_by_logical[logical])
        placeholders = ",".join(["%s"] * len(columns))
        quoted = ",".join(f"`{col}`" for col in columns)
        cur.execute(f"INSERT INTO my_collection ({quoted}) VALUES ({placeholders})", values)


def iter_covers(missing_only=False, anime_id=None, limit=None):
    cols = get_table_columns("bangumi_anime")
    image_cols = [col for col in ("image_large", "image_small") if col in cols]
    if not image_cols:
        return []
    select_cols = ["id", *image_cols]
    if "cover_local_path" in cols:
        select_cols.append("cover_local_path")
    sql = f"SELECT {', '.join(f'`{c}`' for c in select_cols)} FROM bangumi_anime WHERE (" + " OR ".join(f"`{c}` IS NOT NULL" for c in image_cols) + ")"
    params = []
    if missing_only and "cover_local_path" in cols:
        sql += " AND (cover_local_path IS NULL OR cover_local_path = '')"
    if anime_id:
        sql += " AND id=%s"
        params.append(anime_id)
    sql += " ORDER BY id"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def update_cover_status(anime_id: int, local_path: str | None, status: str):
    cols = get_table_columns("bangumi_anime")
    assignments = []
    params = []
    if "cover_local_path" in cols and local_path:
        assignments.append("cover_local_path=%s")
        params.append(local_path)
    if "cover_cache_status" in cols:
        assignments.append("cover_cache_status=%s")
        params.append(status)
    if "cover_cached_at" in cols and status == "cached":
        assignments.append("cover_cached_at=NOW()")
    if "updated_at" in cols:
        assignments.append("updated_at=CURRENT_TIMESTAMP")
    if not assignments:
        return
    params.append(anime_id)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE bangumi_anime SET {', '.join(assignments)} WHERE id=%s", params)
