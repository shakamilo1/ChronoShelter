from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from importer.bangumi_data_sync import DATA_FILE, load_entries
from app.schema_utils import get_table_columns
from importer.image_cache import cache_cover
from importer.merge_engine import merge_subjects

UPSERT_SQL = """
INSERT INTO subjects (
 id, name_jp, name_cn, name_en, type, platform, air_date, air_year, air_month,
 air_weekday, raw_air_date, eps, summary, rating_score, rating_count, `rank`,
 image_small, image_large, cover_local_path, cover_cache_status, cover_cached_at, broadcast, sites_json, tags_json, meta_tags_json, infobox_json, raw_infobox, nsfw
) VALUES (
 %(id)s, %(name_jp)s, %(name_cn)s, %(name_en)s, %(type)s, %(platform)s, %(air_date)s,
 %(air_year)s, %(air_month)s, %(air_weekday)s, %(raw_air_date)s, %(eps)s, %(summary)s,
 %(rating_score)s, %(rating_count)s, %(rank)s, %(image_small)s, %(image_large)s,
 %(cover_local_path)s, %(cover_cache_status)s, %(cover_cached_at)s, %(broadcast)s, %(sites_json)s, %(tags_json)s, %(meta_tags_json)s, %(infobox_json)s, %(raw_infobox)s, %(nsfw)s
)
ON DUPLICATE KEY UPDATE
 name_jp=COALESCE(NULLIF(VALUES(name_jp), ''), name_jp),
 name_cn=COALESCE(NULLIF(VALUES(name_cn), ''), name_cn),
 name_en=COALESCE(NULLIF(VALUES(name_en), ''), name_en),
 type=COALESCE(NULLIF(VALUES(type), ''), type),
 platform=COALESCE(VALUES(platform), platform),
 air_date=COALESCE(VALUES(air_date), air_date),
 air_year=COALESCE(VALUES(air_year), air_year),
 air_month=COALESCE(VALUES(air_month), air_month),
 air_weekday=COALESCE(NULLIF(VALUES(air_weekday), ''), air_weekday),
 raw_air_date=COALESCE(NULLIF(VALUES(raw_air_date), ''), raw_air_date),
 eps=COALESCE(VALUES(eps), eps),
 summary=COALESCE(NULLIF(VALUES(summary), ''), summary),
 rating_score=COALESCE(VALUES(rating_score), rating_score),
 rating_count=COALESCE(VALUES(rating_count), rating_count),
 `rank`=COALESCE(VALUES(`rank`), `rank`),
 image_small=COALESCE(NULLIF(VALUES(image_small), ''), image_small),
 image_large=COALESCE(NULLIF(VALUES(image_large), ''), image_large),
 cover_local_path=COALESCE(NULLIF(VALUES(cover_local_path), ''), cover_local_path),
 cover_cache_status=COALESCE(NULLIF(VALUES(cover_cache_status), ''), cover_cache_status),
 cover_cached_at=COALESCE(VALUES(cover_cached_at), cover_cached_at),
 broadcast=COALESCE(NULLIF(VALUES(broadcast), ''), broadcast),
 sites_json=COALESCE(VALUES(sites_json), sites_json),
 tags_json=COALESCE(VALUES(tags_json), tags_json),
 meta_tags_json=COALESCE(VALUES(meta_tags_json), meta_tags_json),
 infobox_json=COALESCE(VALUES(infobox_json), infobox_json),
 raw_infobox=COALESCE(NULLIF(VALUES(raw_infobox), ''), raw_infobox),
 nsfw=VALUES(nsfw),
 updated_at=CURRENT_TIMESTAMP
"""

SAFE_UPSERT_SQL = """
INSERT INTO subjects (
 id, name_jp, name_cn, name_en, type, platform, air_date, air_year, air_month,
 air_weekday, raw_air_date, eps, summary, rating_score, rating_count, `rank`,
 image_small, image_large, cover_local_path, cover_cache_status, cover_cached_at, broadcast, sites_json, tags_json, meta_tags_json, infobox_json, raw_infobox, nsfw
) VALUES (
 %(id)s, %(name_jp)s, %(name_cn)s, %(name_en)s, %(type)s, %(platform)s, %(air_date)s,
 %(air_year)s, %(air_month)s, %(air_weekday)s, %(raw_air_date)s, %(eps)s, %(summary)s,
 %(rating_score)s, %(rating_count)s, %(rank)s, %(image_small)s, %(image_large)s,
 %(cover_local_path)s, %(cover_cache_status)s, %(cover_cached_at)s, %(broadcast)s, %(sites_json)s, %(tags_json)s, %(meta_tags_json)s, %(infobox_json)s, %(raw_infobox)s, %(nsfw)s
)
ON DUPLICATE KEY UPDATE
 name_jp=COALESCE(NULLIF(name_jp, ''), NULLIF(VALUES(name_jp), '')),
 name_cn=COALESCE(NULLIF(name_cn, ''), NULLIF(VALUES(name_cn), '')),
 name_en=COALESCE(NULLIF(name_en, ''), NULLIF(VALUES(name_en), '')),
 type=COALESCE(NULLIF(type, ''), NULLIF(VALUES(type), '')),
 platform=COALESCE(platform, VALUES(platform)),
 air_date=COALESCE(air_date, VALUES(air_date)),
 air_year=COALESCE(air_year, VALUES(air_year)),
 air_month=COALESCE(air_month, VALUES(air_month)),
 air_weekday=COALESCE(NULLIF(air_weekday, ''), NULLIF(VALUES(air_weekday), '')),
 raw_air_date=COALESCE(NULLIF(raw_air_date, ''), NULLIF(VALUES(raw_air_date), '')),
 eps=COALESCE(eps, VALUES(eps)),
 summary=COALESCE(NULLIF(summary, ''), NULLIF(VALUES(summary), '')),
 rating_score=COALESCE(rating_score, VALUES(rating_score)),
 rating_count=COALESCE(rating_count, VALUES(rating_count)),
 `rank`=COALESCE(`rank`, VALUES(`rank`)),
 image_small=COALESCE(NULLIF(image_small, ''), NULLIF(VALUES(image_small), '')),
 image_large=COALESCE(NULLIF(image_large, ''), NULLIF(VALUES(image_large), '')),
 cover_local_path=COALESCE(NULLIF(cover_local_path, ''), NULLIF(VALUES(cover_local_path), '')),
 cover_cache_status=COALESCE(NULLIF(cover_cache_status, ''), NULLIF(VALUES(cover_cache_status), '')),
 cover_cached_at=COALESCE(cover_cached_at, VALUES(cover_cached_at)),
 broadcast=COALESCE(NULLIF(broadcast, ''), NULLIF(VALUES(broadcast), '')),
 sites_json=COALESCE(sites_json, VALUES(sites_json)),
 tags_json=COALESCE(tags_json, VALUES(tags_json)),
 meta_tags_json=COALESCE(meta_tags_json, VALUES(meta_tags_json)),
 infobox_json=COALESCE(infobox_json, VALUES(infobox_json)),
 raw_infobox=COALESCE(NULLIF(raw_infobox, ''), NULLIF(VALUES(raw_infobox), '')),
 nsfw=nsfw,
 updated_at=CURRENT_TIMESTAMP
"""

OPTIONAL_MIGRATION_HINTS = {
    "images": "Archive subjects.images column is missing",
    "tags": "Archive subjects.tags column is missing",
    "meta": "Archive subjects.meta column is missing",
    "infobox": "Archive subjects.infobox column is missing",
    "raw_json": "Archive subjects.raw_json column is missing",
}


def build_upsert_sql(row: dict, existing_columns: set[str], safe_mode: bool = False) -> tuple[str, dict]:
    if "id" not in existing_columns:
        raise RuntimeError("subjects.id column is required before importing.")
    writable = [key for key, value in row.items() if key in existing_columns]
    missing = [key for key in row if key not in existing_columns and key in OPTIONAL_MIGRATION_HINTS]
    for key in missing:
        print(f"warning: subjects.{key} missing; 需要执行 migration {OPTIONAL_MIGRATION_HINTS[key]}", file=sys.stderr)
    quoted = [f"`{col}`" if col == "rank" else col for col in writable]
    values = [f"%({col})s" for col in writable]
    updates = []
    for col in writable:
        if col == "id":
            continue
        q = f"`{col}`" if col == "rank" else col
        if safe_mode:
            if col in {"nsfw"}:
                updates.append(f"{q}={q}")
            elif col.endswith("_json"):
                updates.append(f"{q}=COALESCE({q}, VALUES({q}))")
            elif col in {"platform", "date", "air_date", "air_year", "air_month", "eps", "score", "rating_score", "rating_count", "rank", "cover_cached_at"}:
                updates.append(f"{q}=COALESCE({q}, VALUES({q}))")
            else:
                updates.append(f"{q}=COALESCE(NULLIF({q}, ''), NULLIF(VALUES({q}), ''))")
        else:
            if col in {"platform", "date", "air_date", "air_year", "air_month", "eps", "score", "rating_score", "rating_count", "rank", "cover_cached_at"}:
                updates.append(f"{q}=COALESCE(VALUES({q}), {q})")
            elif col.endswith("_json"):
                updates.append(f"{q}=COALESCE(VALUES({q}), {q})")
            else:
                updates.append(f"{q}=COALESCE(NULLIF(VALUES({q}), ''), {q})")
    if "updated_at" in existing_columns:
        updates.append("updated_at=CURRENT_TIMESTAMP")
    sql = f"INSERT INTO subjects ({', '.join(quoted)}) VALUES ({', '.join(values)}) ON DUPLICATE KEY UPDATE {', '.join(updates)}"
    return sql, {key: row[key] for key in writable}

def normalize_subject(subject: dict, bangumi_data_entry: dict | None = None, cache_images: bool = False) -> dict:
    model = merge_subjects(subject, bangumi_data_entry)
    cover_local_path = None
    if cache_images:
        cover_local_path = cache_cover(model.id, model.image_large or model.image_small)
    return {
        "id": model.id,
        "name": model.name_jp,
        "name_cn": model.name_cn,
        "type": int(model.type) if model.type and str(model.type).isdigit() else None,
        "date": model.air_date,
        "eps": model.eps,
        "summary": model.summary,
        "score": model.rating_score,
        "rating_count": model.rating_count,
        "rank": model.rank,
        "images": json.dumps({"small": model.image_small, "large": model.image_large}, ensure_ascii=False),
        "tags": json.dumps(model.tags or [], ensure_ascii=False),
        "meta": json.dumps({"meta_tags": model.meta_tags or [], "sites": model.sites or [], "broadcast": model.broadcast, "nsfw": model.nsfw}, ensure_ascii=False),
        "infobox": json.dumps(model.infobox or [], ensure_ascii=False),
        "raw_json": json.dumps(subject, ensure_ascii=False),
    }


def iter_subjects(path, limit=None, only_id=None):
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            subject = json.loads(line)
            if only_id and int(subject.get("id", -1)) != only_id:
                continue
            yield subject
            if limit is not None:
                limit -= 1
                if limit <= 0:
                    break


def import_file(path, limit=None, dry_run=False, only_id=None, safe_mode=False, bangumi_data_file=None, cache_images=False):
    imported = skipped = errors = 0
    bangumi_data = load_entries(Path(bangumi_data_file) if bangumi_data_file else DATA_FILE)
    iterable = iter_subjects(path, limit=limit, only_id=only_id)
    if tqdm:
        iterable = tqdm(iterable, unit="line")
    existing_columns = get_table_columns("subjects") if not dry_run else set()
    if dry_run:
        conn_ctx = None
    else:
        from app.database import get_connection
        conn_ctx = get_connection()
    conn = conn_ctx.__enter__() if conn_ctx else None
    try:
        for subject in iterable:
            try:
                if int(subject.get("type", -1)) != 2:
                    skipped += 1
                    continue
                row = normalize_subject(subject, bangumi_data.get(int(subject["id"])), cache_images=cache_images)
                if dry_run:
                    imported += 1
                    continue
                sql, params = build_upsert_sql(row, existing_columns, safe_mode=safe_mode)
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"error subject={subject.get('id')}: {exc}", file=sys.stderr)
    finally:
        if conn_ctx:
            conn_ctx.__exit__(None, None, None)
    print(f"imported={imported} skipped={skipped} errors={errors}")
    return imported, skipped, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--id", type=int, dest="only_id")
    parser.add_argument("--safe-mode", action="store_true", help="Only fill missing fields; never overwrite existing names or infobox.")
    parser.add_argument("--bangumi-data", help="Optional bangumi-data JSON path; defaults to data/bangumi_data.json when present.")
    parser.add_argument("--cache-covers", action="store_true", help="Download missing covers during import. Off by default to keep import fast/non-blocking.")
    args = parser.parse_args()
    import_file(args.file, args.limit, args.dry_run, args.only_id, args.safe_mode, args.bangumi_data, args.cache_covers)

if __name__ == "__main__":
    main()
