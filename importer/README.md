# Importer status

ChronoShelter now uses Bangumi Archive public tables in `chrono_bangumi` (`subjects`, `episodes`, `persons`, `characters`, relation tables) and user collections in `chrono_library.collections`.

`import_subject_jsonlines.py` is retained only as a lightweight compatibility/debug importer that can upsert compatible fields into `subjects`. The recommended public update path is `tools/archive_update.py` with a staged temporary public database.

## Safe Archive update flow

```bash
python tools/archive_update.py --download --url <release.zip>
python tools/archive_update.py --extract
python tools/archive_update.py --create-temp-db --temp-db chrono_bangumi_tmp
python tools/archive_update.py --validate --temp-db chrono_bangumi_tmp
python tools/archive_update.py --plan-swap --temp-db chrono_bangumi_tmp
```

The Archive updater never touches `chrono_library.collections`.
