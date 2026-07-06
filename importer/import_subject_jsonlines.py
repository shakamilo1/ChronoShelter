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

from importer.infobox_parser import parse_infobox
from importer.normalizer import (
    choose_name_en,
    infobox_value,
    normalize_air_date,
    normalize_eps,
    normalize_tags,
    rating_count_from_score_details,
)

UPSERT_SQL = """
INSERT INTO bangumi_anime (
 id, name_jp, name_cn, name_en, type, platform, air_date, air_year, air_month,
 air_weekday, raw_air_date, eps, summary, rating_score, rating_count, `rank`,
 image_small, image_large, tags_json, meta_tags_json, infobox_json, raw_infobox, nsfw
) VALUES (
 %(id)s, %(name_jp)s, %(name_cn)s, %(name_en)s, %(type)s, %(platform)s, %(air_date)s,
 %(air_year)s, %(air_month)s, %(air_weekday)s, %(raw_air_date)s, %(eps)s, %(summary)s,
 %(rating_score)s, %(rating_count)s, %(rank)s, %(image_small)s, %(image_large)s,
 %(tags_json)s, %(meta_tags_json)s, %(infobox_json)s, %(raw_infobox)s, %(nsfw)s
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
 tags_json=COALESCE(VALUES(tags_json), tags_json),
 meta_tags_json=COALESCE(VALUES(meta_tags_json), meta_tags_json),
 infobox_json=COALESCE(VALUES(infobox_json), infobox_json),
 raw_infobox=COALESCE(NULLIF(VALUES(raw_infobox), ''), raw_infobox),
 nsfw=VALUES(nsfw),
 updated_at=CURRENT_TIMESTAMP
"""


def normalize_subject(subject: dict) -> dict:
    infobox = parse_infobox(subject.get("infobox"))
    air_raw = subject.get("date") or infobox_value(infobox, "放送开始")
    air_date, air_year, air_month, raw_air_date = normalize_air_date(air_raw)
    rating = subject.get("rating") or {}
    images = subject.get("images") or {}
    return {
        "id": int(subject["id"]),
        "name_jp": subject.get("name") or None,
        "name_cn": subject.get("name_cn") or None,
        "name_en": choose_name_en(infobox),
        "type": str(subject.get("type")) if subject.get("type") is not None else None,
        "platform": subject.get("platform"),
        "air_date": air_date,
        "air_year": air_year,
        "air_month": air_month,
        "air_weekday": infobox_value(infobox, "放送星期"),
        "raw_air_date": raw_air_date,
        "eps": normalize_eps(subject.get("eps") or infobox_value(infobox, "话数")),
        "summary": subject.get("summary") or None,
        "rating_score": rating.get("score") or None,
        "rating_count": rating_count_from_score_details(rating.get("score_details")),
        "rank": subject.get("rank"),
        "image_small": images.get("small"),
        "image_large": images.get("large") or images.get("common"),
        "tags_json": json.dumps(normalize_tags(subject.get("tags")), ensure_ascii=False),
        "meta_tags_json": json.dumps(subject.get("meta_tags") or [], ensure_ascii=False),
        "infobox_json": json.dumps(infobox, ensure_ascii=False),
        "raw_infobox": subject.get("infobox") or None,
        "nsfw": bool(subject.get("nsfw", False)),
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


def import_file(path, limit=None, dry_run=False, only_id=None):
    imported = skipped = errors = 0
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
                row = normalize_subject(subject)
                if dry_run:
                    imported += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(UPSERT_SQL, row)
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
    args = parser.parse_args()
    import_file(args.file, args.limit, args.dry_run, args.only_id)

if __name__ == "__main__":
    main()
