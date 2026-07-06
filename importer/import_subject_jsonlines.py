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
from importer.image_cache import cache_cover
from importer.merge_engine import merge_subjects

UPSERT_SQL = """
INSERT INTO bangumi_anime (
 id, name_jp, name_cn, name_en, type, platform, air_date, air_year, air_month,
 air_weekday, raw_air_date, eps, summary, rating_score, rating_count, `rank`,
 image_small, image_large, cover_local_path, broadcast, tags_json, meta_tags_json, infobox_json, raw_infobox, nsfw
) VALUES (
 %(id)s, %(name_jp)s, %(name_cn)s, %(name_en)s, %(type)s, %(platform)s, %(air_date)s,
 %(air_year)s, %(air_month)s, %(air_weekday)s, %(raw_air_date)s, %(eps)s, %(summary)s,
 %(rating_score)s, %(rating_count)s, %(rank)s, %(image_small)s, %(image_large)s,
 %(cover_local_path)s, %(broadcast)s, %(tags_json)s, %(meta_tags_json)s, %(infobox_json)s, %(raw_infobox)s, %(nsfw)s
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
 broadcast=COALESCE(NULLIF(VALUES(broadcast), ''), broadcast),
 tags_json=COALESCE(VALUES(tags_json), tags_json),
 meta_tags_json=COALESCE(VALUES(meta_tags_json), meta_tags_json),
 infobox_json=COALESCE(VALUES(infobox_json), infobox_json),
 raw_infobox=COALESCE(NULLIF(VALUES(raw_infobox), ''), raw_infobox),
 nsfw=VALUES(nsfw),
 updated_at=CURRENT_TIMESTAMP
"""

SAFE_UPSERT_SQL = """
INSERT INTO bangumi_anime (
 id, name_jp, name_cn, name_en, type, platform, air_date, air_year, air_month,
 air_weekday, raw_air_date, eps, summary, rating_score, rating_count, `rank`,
 image_small, image_large, cover_local_path, broadcast, tags_json, meta_tags_json, infobox_json, raw_infobox, nsfw
) VALUES (
 %(id)s, %(name_jp)s, %(name_cn)s, %(name_en)s, %(type)s, %(platform)s, %(air_date)s,
 %(air_year)s, %(air_month)s, %(air_weekday)s, %(raw_air_date)s, %(eps)s, %(summary)s,
 %(rating_score)s, %(rating_count)s, %(rank)s, %(image_small)s, %(image_large)s,
 %(cover_local_path)s, %(broadcast)s, %(tags_json)s, %(meta_tags_json)s, %(infobox_json)s, %(raw_infobox)s, %(nsfw)s
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
 broadcast=COALESCE(NULLIF(broadcast, ''), NULLIF(VALUES(broadcast), '')),
 tags_json=COALESCE(tags_json, VALUES(tags_json)),
 meta_tags_json=COALESCE(meta_tags_json, VALUES(meta_tags_json)),
 infobox_json=COALESCE(infobox_json, VALUES(infobox_json)),
 raw_infobox=COALESCE(NULLIF(raw_infobox, ''), NULLIF(VALUES(raw_infobox), '')),
 nsfw=nsfw,
 updated_at=CURRENT_TIMESTAMP
"""

def normalize_subject(subject: dict, bangumi_data_entry: dict | None = None, cache_images: bool = False) -> dict:
    model = merge_subjects(subject, bangumi_data_entry)
    cover_local_path = None
    if cache_images:
        cover_local_path = cache_cover(model.id, model.image_large or model.image_small)
    return {
        "id": model.id,
        "name_jp": model.name_jp,
        "name_cn": model.name_cn,
        "name_en": model.name_en,
        "type": model.type,
        "platform": model.platform,
        "air_date": model.air_date,
        "air_year": model.air_year,
        "air_month": model.air_month,
        "air_weekday": model.air_weekday,
        "raw_air_date": model.raw_air_date,
        "eps": model.eps,
        "summary": model.summary,
        "rating_score": model.rating_score,
        "rating_count": model.rating_count,
        "rank": model.rank,
        "image_small": model.image_small,
        "image_large": model.image_large,
        "cover_local_path": cover_local_path,
        "broadcast": model.broadcast,
        "tags_json": json.dumps(model.tags or [], ensure_ascii=False),
        "meta_tags_json": json.dumps(model.meta_tags or [], ensure_ascii=False),
        "infobox_json": json.dumps(model.infobox or [], ensure_ascii=False),
        "raw_infobox": model.raw_infobox,
        "nsfw": model.nsfw,
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
                with conn.cursor() as cur:
                    cur.execute(SAFE_UPSERT_SQL if safe_mode else UPSERT_SQL, row)
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
