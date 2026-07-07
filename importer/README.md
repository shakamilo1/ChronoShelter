# Importer status

ChronoShelter uses Bangumi Archive public tables in `chrono_bangumi` (`subjects`, `episodes`, `persons`, `characters`, relation tables) and user collections in `chrono_library.collections`.

## Import Archive dump directory

```bash
python importer/import_archive_dump.py --dir /path/to/archive-dump --dry-run
python importer/import_archive_dump.py --dir /path/to/archive-dump --table subjects --limit 100
python importer/import_archive_dump.py --dir /path/to/archive-dump
```

Expected files:

- `subject.jsonlines` -> `subjects`
- `episode.jsonlines` -> `episodes`
- `person.jsonlines` -> `persons`
- `character.jsonlines` -> `characters`
- `subject_person.jsonlines` -> `subject_persons`
- `subject_character.jsonlines` -> `subject_characters`
- `subject_relation.jsonlines` -> `subject_relations`
- `person_relation.jsonlines` -> `person_relations`
- `person_character.jsonlines` -> `person_characters`

The importer writes only existing columns and does not create databases or tables.

## Safe Archive update flow

```bash
python tools/archive_update.py --download --url <release.zip>
python tools/archive_update.py --extract
python tools/archive_update.py --create-temp-db --temp-db chrono_bangumi_tmp
python importer/import_archive_dump.py --dir data/archive/extracted --dry-run
python tools/archive_update.py --validate --temp-db chrono_bangumi_tmp
python tools/archive_update.py --plan-swap --temp-db chrono_bangumi_tmp
```

The Archive updater never touches `chrono_library.collections`.
