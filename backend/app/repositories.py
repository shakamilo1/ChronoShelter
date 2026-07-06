import json
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
    return row


def list_anime(q: str | None = None, limit: int = 40, offset: int = 0):
    sql = "SELECT * FROM bangumi_anime"
    params = []
    if q:
        sql += " WHERE name_cn LIKE %s OR name_jp LIKE %s OR name_en LIKE %s"
        like = f"%{q}%"
        params.extend([like, like, like])
    sql += " ORDER BY COALESCE(air_date, STR_TO_DATE(CONCAT(air_year,'-',COALESCE(air_month,1),'-01'), '%Y-%m-%d')) DESC, id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [_hydrate(row) for row in cur.fetchall()]


def get_anime(anime_id: int):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM bangumi_anime WHERE id=%s", (anime_id,))
        return _hydrate(cur.fetchone())
