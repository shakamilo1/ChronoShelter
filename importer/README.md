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
- `subject-persons.jsonlines` -> `subject_persons`
- `subject-characters.jsonlines` -> `subject_characters`
- `subject-relations.jsonlines` -> `subject_relations`
- `person-relations.jsonlines` -> `person_relations`
- `person-characters.jsonlines` -> `person_characters`

The importer writes only existing columns and does not create databases or tables.

## Safe Archive update flow

```bash
python tools/archive_update.py --file archive.zip
# or: python tools/archive_update.py --url <release.zip>
python importer/import_archive_dump.py --dir data/archive/processed --dry-run
python importer/import_archive_dump.py --dir data/archive/processed
python importer/import_archive_dump.py --dir data/archive/processed --batch-size 1000
```

The Archive updater never touches `chrono_library.collections`.
