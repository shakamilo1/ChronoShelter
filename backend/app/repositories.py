import json
from datetime import date
from .database import get_connection


def _loads(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _hydrate(row):
    if not row:
        return None
    row["tags"] = _loads(row.pop("tags_json", None), [])
    row["meta_tags"] = _loads(row.pop("meta_tags_json", None), [])
    row["infobox"] = _loads(row.pop("infobox_json", None), [])
    row["sites"] = _loads(row.pop("sites_json", None), [])
    return row


def list_anime(q: str | None = None, limit: int = 40, offset: int = 0):
    sql = """
        SELECT a.*, c.collected, c.collection_date, c.my_rating
        FROM bangumi_anime a
        LEFT JOIN my_collection c ON c.bangumi_id = a.id
    """
    params = []
    if q:
        sql += " WHERE a.name_cn LIKE %s OR a.name_jp LIKE %s OR a.name_en LIKE %s"
        like = f"%{q}%"
        params.extend([like, like, like])
    sql += " ORDER BY COALESCE(a.air_date, STR_TO_DATE(CONCAT(a.air_year,'-',COALESCE(a.air_month,1),'-01'), '%Y-%m-%d')) DESC, a.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [_hydrate(row) for row in cur.fetchall()]


def get_anime(anime_id: int):
    sql = """
        SELECT a.*, c.id AS collection_id, c.collected, c.collection_date,
               c.media_type, c.subtitle_group, c.source_site, c.my_rating,
               c.notes, c.extra_json
        FROM bangumi_anime a
        LEFT JOIN my_collection c ON c.bangumi_id = a.id
        WHERE a.id=%s
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (anime_id,))
        return _hydrate(cur.fetchone())


def one_click_collect(anime_id: int):
    sql = """
        INSERT INTO my_collection (bangumi_id, collected, collection_date)
        VALUES (%s, TRUE, CURDATE())
        ON DUPLICATE KEY UPDATE
          collected=TRUE,
          collection_date=COALESCE(collection_date, VALUES(collection_date)),
          updated_at=CURRENT_TIMESTAMP
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (anime_id,))


def save_collection(anime_id: int, form: dict):
    collection_date = form.get("collection_date") or None
    my_rating = form.get("my_rating") or None
    if my_rating not in (None, ""):
        my_rating = float(my_rating)
    else:
        my_rating = None
    extra = form.get("extra") or None
    extra_json = json.dumps({"other": extra}, ensure_ascii=False) if extra else None
    collected = form.get("collected") in {"on", "true", "1", "yes"}
    sql = """
        INSERT INTO my_collection (
          bangumi_id, collected, collection_date, media_type, subtitle_group,
          source_site, my_rating, notes, extra_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          collected=VALUES(collected),
          collection_date=VALUES(collection_date),
          media_type=VALUES(media_type),
          subtitle_group=VALUES(subtitle_group),
          source_site=VALUES(source_site),
          my_rating=VALUES(my_rating),
          notes=VALUES(notes),
          extra_json=VALUES(extra_json),
          updated_at=CURRENT_TIMESTAMP
    """
    params = (
        anime_id,
        collected,
        collection_date,
        form.get("media_type") or None,
        form.get("subtitle_group") or None,
        form.get("source_site") or None,
        my_rating,
        form.get("notes") or None,
        extra_json,
    )
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def iter_covers(missing_only=False, anime_id=None, limit=None):
    sql = "SELECT id, image_large, image_small, cover_local_path FROM bangumi_anime WHERE (image_large IS NOT NULL OR image_small IS NOT NULL)"
    params = []
    if missing_only:
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
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE bangumi_anime
            SET cover_local_path=COALESCE(%s, cover_local_path),
                cover_cache_status=%s,
                cover_cached_at=CASE WHEN %s='cached' THEN NOW() ELSE cover_cached_at END,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (local_path, status, status, anime_id),
        )
