# ChronoShelter current schema expectations

ChronoShelter must support existing MariaDB databases. Always run `python tools/inspect_schema.py` before migrations.

## bangumi_anime

### Minimum required to browse

- `id` (required primary identifier)
- `name_jp` or `name_cn` (at least one title is needed for display)

### Recommended public-library fields

- Titles: `name_jp`, `name_cn`, `name_en`
- Airing: `air_date`, `air_year`, `air_month`, `air_weekday`, `raw_air_date`, `broadcast`
- Metadata: `eps`, `summary`, `rating_score`, `rating_count`, `rank`, `nsfw`
- Images: `image_small`, `image_large`, `cover_local_path`, `cover_cache_status`, `cover_cached_at`
- JSON fields: `tags_json`, `meta_tags_json`, `infobox_json`, `sites_json`
- Raw fields: `raw_infobox`

### Legacy-compatible fields

If the new JSON columns do not exist, the web layer can read legacy fields:

- `tags_json` fallback: `tags`
- `meta_tags_json` fallback: `meta_tags`
- `infobox_json` fallback: `infobox`
- `raw_infobox` is optional; if absent, pages do not fail.
- `aka_names` is allowed to exist but is not required for the MVP.

### Migration priority

Must migrate for importer writes:

- `id`

Optional but recommended migration:

- `cover_local_path`, `cover_cache_status`, `cover_cached_at`
- `broadcast`, `sites_json`
- `tags_json`, `meta_tags_json`, `infobox_json`, `raw_infobox`

The importer checks actual columns before writing and only writes columns that exist. Missing optional columns produce warnings that point to migration files.

## my_collection

`my_collection` is user-owned data. Do not drop, truncate, rebuild, or rename it automatically.

### Identifier field

At least one of these fields must exist so the app can link a collection row to `bangumi_anime.id`:

- `bangumi_id`
- `anime_id`
- `subject_id`

If none exists, one-click collect and collection editing cannot safely work until a migration adds a nullable mapping field.

### Logical fields and compatible old names

- Collected status: `collected` / `is_collected`
- Collection date: `collection_date` / `collect_date` / `created_at` / `date`
- Media type: `media_type` / `medium` / `media`
- Subtitle group: `subtitle_group` / `subgroup` / `fansub`
- Source site: `source_site` / `source` / `site`
- Personal rating: `my_rating` / `rating`
- Notes: `notes` / `note` / `remark`
- Other data: `extra_json` / `extra` / `other`

### Migration rules

- Only use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for existing `my_collection`.
- All added fields must be nullable.
- Existing notes and personal ratings must remain untouched unless the user saves the edit form.
- Always back up first with `mysqldump --single-transaction`.

## Read-only inspection

Run:

```bash
python tools/inspect_schema.py
```

The command prints the columns and row counts for `bangumi_anime` and `my_collection` and never modifies the database.
