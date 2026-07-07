import json
from .archive_mapper import normalize_subject_row
from .collection_mapper import build_collection_field_map, normalize_collection_row
from .database import get_connection, library_database_name, public_database_name
from .schema_utils import get_table_columns, table_exists


def _collection_field_map():
    return build_collection_field_map(get_table_columns("collections", library_database_name()))


def _fetch_collections(subject_ids):
    if not subject_ids or not table_exists("collections", library_database_name()):
        return {}
    fmap = _collection_field_map()
    if not fmap.id_field:
        return {}
    placeholders = ",".join(["%s"] * len(subject_ids))
    with get_connection(library_database_name()) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM collections WHERE `{fmap.id_field}` IN ({placeholders})", subject_ids)
        rows = cur.fetchall()
    return {int(row[fmap.id_field]): normalize_collection_row(row, fmap) for row in rows if row.get(fmap.id_field) is not None}


def _merge_collection(subject_row, collection_map):
    subject_id = int(subject_row["id"])
    merged = normalize_subject_row(subject_row)
    merged.update(collection_map.get(subject_id, normalize_collection_row(None, _collection_field_map())))
    return merged


def list_anime(q: str | None = None, limit: int = 40, offset: int = 0):
    cols = get_table_columns("subjects", public_database_name())
    sql = "SELECT * FROM subjects WHERE type=2" if "type" in cols else "SELECT * FROM subjects"
    params = []
    if q:
        clauses = []
        for col in ("name_cn", "name"):
            if col in cols:
                clauses.append(f"`{col}` LIKE %s")
                params.append(f"%{q}%")
        if clauses:
            sql += " AND (" + " OR ".join(clauses) + ")" if "type" in cols else " WHERE " + " OR ".join(clauses)
    if "date" in cols:
        sql += " ORDER BY date DESC, id DESC LIMIT %s OFFSET %s"
    else:
        sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    collections = _fetch_collections([int(row["id"]) for row in rows])
    return [_merge_collection(row, collections) for row in rows]


def get_anime(subject_id: int):
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM subjects WHERE id=%s", (subject_id,))
        row = cur.fetchone()
    if not row:
        return None
    return _merge_collection(row, _fetch_collections([subject_id]))


def list_episodes(subject_id: int, limit: int = 200):
    if not table_exists("episodes", public_database_name()):
        return []
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM episodes WHERE subject_id=%s ORDER BY COALESCE(sort, id) LIMIT %s", (subject_id, limit))
        return cur.fetchall()


def list_subject_persons(subject_id: int, limit: int = 80):
    if not table_exists("subject_persons", public_database_name()) or not table_exists("persons", public_database_name()):
        return []
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT sp.relation, p.*
            FROM subject_persons sp
            JOIN persons p ON p.id=sp.person_id
            WHERE sp.subject_id=%s
            LIMIT %s
            """,
            (subject_id, limit),
        )
        return cur.fetchall()


def list_subject_characters(subject_id: int, limit: int = 80):
    if not table_exists("subject_characters", public_database_name()) or not table_exists("characters", public_database_name()):
        return []
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT sc.relation, c.*
            FROM subject_characters sc
            JOIN characters c ON c.id=sc.character_id
            WHERE sc.subject_id=%s
            LIMIT %s
            """,
            (subject_id, limit),
        )
        return cur.fetchall()


def one_click_collect(subject_id: int):
    if not table_exists("collections", library_database_name()):
        raise RuntimeError("collections table does not exist. Run schema inspection and a safe migration first.")
    fmap = _collection_field_map()
    if not fmap.id_field:
        raise RuntimeError("collections needs a subject_id/bangumi_id/anime_id column for collection mapping.")
    with get_connection(library_database_name()) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM collections WHERE `{fmap.id_field}`=%s LIMIT 1", (subject_id,))
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
                params.append(subject_id)
                cur.execute(f"UPDATE collections SET {', '.join(assignments)} WHERE `{fmap.id_field}`=%s", params)
            return
        columns = [fmap.id_field]
        values = [subject_id]
        if fmap.collected:
            columns.append(fmap.collected)
            values.append(True)
        if fmap.collection_date and fmap.collection_date not in {"created_at"}:
            columns.append(fmap.collection_date)
            values.append(None)
        placeholders = ",".join(["%s"] * len(columns))
        quoted = ",".join(f"`{col}`" for col in columns)
        cur.execute(f"INSERT INTO collections ({quoted}) VALUES ({placeholders})", values)
        if fmap.collection_date and fmap.collection_date not in {"created_at"}:
            cur.execute(f"UPDATE collections SET `{fmap.collection_date}`=CURDATE() WHERE `{fmap.id_field}`=%s AND `{fmap.collection_date}` IS NULL", (subject_id,))


def save_collection(subject_id: int, form: dict):
    if not table_exists("collections", library_database_name()):
        raise RuntimeError("collections table does not exist. Run schema inspection and a safe migration first.")
    fmap = _collection_field_map()
    if not fmap.id_field:
        raise RuntimeError("collections needs a subject_id/bangumi_id/anime_id column for collection mapping.")
    values_by_logical = {
        "collected": form.get("collected") in {"on", "true", "1", "yes"},
        "collection_date": form.get("collection_date") or None,
        "media_type": form.get("media_type") or None,
        "subtitle_group": form.get("subtitle_group") or None,
        "source_site": form.get("source_site") or None,
        "my_rating": float(form["my_rating"]) if form.get("my_rating") not in (None, "") else None,
        "notes": form.get("notes") or None,
        "progress": form.get("progress") or None,
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
        "progress": fmap.progress,
        "extra": fmap.extra,
    }
    with get_connection(library_database_name()) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM collections WHERE `{fmap.id_field}`=%s LIMIT 1", (subject_id,))
        existing = cur.fetchone()
        if existing:
            assignments = []
            params = []
            for logical, col in logical_to_column.items():
                if col:
                    assignments.append(f"`{col}`=%s")
                    params.append(values_by_logical[logical])
            if assignments:
                params.append(subject_id)
                cur.execute(f"UPDATE collections SET {', '.join(assignments)} WHERE `{fmap.id_field}`=%s", params)
            return
        columns = [fmap.id_field]
        values = [subject_id]
        for logical, col in logical_to_column.items():
            if col:
                columns.append(col)
                values.append(values_by_logical[logical])
        placeholders = ",".join(["%s"] * len(columns))
        quoted = ",".join(f"`{col}`" for col in columns)
        cur.execute(f"INSERT INTO collections ({quoted}) VALUES ({placeholders})", values)


def iter_covers(missing_only=False, anime_id=None, limit=None):
    cols = get_table_columns("subjects", public_database_name())
    sql = "SELECT id FROM subjects"
    params = []
    clauses = []
    if "type" in cols:
        clauses.append("type=2")
    if anime_id:
        clauses.append("id=%s")
        params.append(anime_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with get_connection(public_database_name()) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def update_cover_status(anime_id: int, local_path: str | None, status: str):
    # Archive public tables are replaceable snapshots. Cover cache status is intentionally not written there.
    return None
