# ChronoShelter data-layer expectations

This PR only changes application architecture. It must not execute database modifications.

## Databases

- `chrono_bangumi`: public Bangumi Archive data; can be fully rebuilt from Archive releases.
- `chrono_library`: personal data; must be permanently preserved.

## Public database: chrono_bangumi

Use Bangumi Archive table names exactly:

- `subjects`
- `episodes`
- `persons`
- `characters`
- `subject_persons`
- `subject_characters`
- `subject_relations`
- `person_characters`
- `person_relations`

Do not create `bangumi_anime` or an `anime` table.

The poster wall reads `subjects(type=2)`. Detail pages read one subject plus related episodes, persons, characters, and collection data.

## Personal database: chrono_library

Use `collections` for user-owned data. Archive updates must never rebuild or overwrite this table.

Recommended logical fields:

- `subject_id`
- `collected` / `is_collected`
- `collection_date` / `collect_date` / `created_at` / `date`
- `media_type` / `medium` / `media`
- `subtitle_group` / `subgroup` / `fansub`
- `source_site` / `source` / `site`
- `my_rating` / `rating`
- `notes` / `note` / `remark`
- `progress` / `watch_progress` / `watched_eps`
- `extra_json` / `extra` / `other`

The application uses `backend/app/collection_mapper.py` to map old field names to these logical fields.

## Inspection

```bash
python tools/inspect_schema.py
```

The tool reads both configured databases and prints Archive table and `collections` columns/row counts. It does not modify data.
