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

The PHP collection layer writes the canonical `chrono_library.collections` fields directly; legacy field-name mapping is no longer part of the web runtime.

## Inspection

```bash
python tools/inspect_schema.py
```

The tool reads both configured databases and prints Archive table and `collections` columns/row counts. It does not modify data.

## SQL initialization drafts

Database landing SQL is intentionally split into reviewable files under `sql/`:

- `sql/create_chrono_bangumi_tables.sql`: contains `CREATE TABLE` statements for the manually selected `chrono_bangumi` public Archive cache database, with field names and small unsigned integer widths aligned to the official Bangumi Archive README model, including `platform`, `position`, and relation-type enum columns.
- `sql/create_chrono_library_tables.sql`: contains `CREATE TABLE` statements for the manually selected `chrono_library` personal tables (`collections` plus optional `cover_cache`) without any Bangumi public fields in `collections`.
- `sql/create_chrono_bangumi_indexes.sql`: creates recommended lookup indexes for `chrono_bangumi`.
- `sql/create_chrono_library_indexes.sql`: creates recommended lookup indexes for `chrono_library`.

These SQL files are generated for manual review/execution only. They must not be run by the application automatically, contain no `CREATE DATABASE` statements, and never reference the legacy `chrono_shelter` database.

## Importer compatibility check

`importer/import_archive_dump.py` imports only columns that exist in the destination table. The generated `chrono_bangumi` SQL uses Archive field names directly, so current Archive keys from the nine jsonlines files match the writable columns:

- `subjects`: `id`, `type`, `name`, `name_cn`, `infobox`, `platform`, `summary`, `tags`, `meta_tags`, `score`, `score_details`, `rank`, `favorite`, `date`, `nsfw`, `series`
- `episodes`: `id`, `name`, `name_cn`, `description`, `airdate`, `disc`, `duration`, `subject_id`, `sort`, `type`
- `persons`: `id`, `name`, `type`, `career`, `infobox`, `summary`, `comments`, `collects`
- `characters`: `id`, `role`, `name`, `infobox`, `summary`, `comments`, `collects`
- relation tables: Archive relation keys are preserved (`subject_id`, `person_id`, `character_id`, `related_subject_id`, `related_person_id`, `relation_type`, `position`, `appear_eps`, `order`, `summary`, `person_type`, `spoiler`, `ended`).
