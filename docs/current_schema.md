# ChronoShelter Archive schema expectations

ChronoShelter now uses Bangumi Archive public tables and a separate personal `my_collection` table. Always run `python tools/inspect_schema.py` before migrations or Archive updates.

## Public Archive tables

The public database uses the Archive entity model and may be periodically rebuilt from Archive releases:

- `subject`
- `episode`
- `person`
- `character`
- `subject_person`
- `subject_character`
- `subject_relation`
- `person_character`
- `person_relation`

Do not create new `bangumi_anime` tables. Old deployments may still have `bangumi_anime`, but the current app does not require it.

## subject

### Minimum required for the poster wall

- `id`
- `type` (`type=2` means anime)
- `name` or `name_cn`

### Recommended fields

- `summary`
- `date`
- `eps`
- `score`
- `rating_count`
- `rank`
- `images` JSON
- `tags` JSON
- `infobox` JSON
- `meta` JSON
- `raw_json` JSON

## Detail-page related tables

- `episode.subject_id` links episodes to `subject.id`.
- `subject_person.subject_id` + `subject_person.person_id` links staff/person rows.
- `subject_character.subject_id` + `subject_character.character_id` links character rows.
- Relation tables are public Archive data and must never contain personal collection data.

## my_collection

`my_collection` is user-owned data. It is not rebuilt by Archive updates and must never be dropped/truncated/rebuilt by the Archive updater.

### Identifier field

At least one of these fields must exist so the app can link collection rows to `subject.id`:

- `subject_id` preferred
- `bangumi_id` legacy compatible
- `anime_id` legacy compatible

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
- Existing notes and personal ratings remain untouched unless the user saves the edit form.
- Always back up first with `mysqldump --single-transaction`.

## Read-only inspection

```bash
python tools/inspect_schema.py
```

The command prints columns and row counts for Archive public tables and `my_collection` and never modifies the database.
