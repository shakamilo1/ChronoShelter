# Importer status

ChronoShelter now uses Bangumi Archive public tables (`subject`, `episode`, `person`, `character`, relation tables) instead of `bangumi_anime`.

`import_subject_jsonlines.py` remains as a lightweight compatibility/debug importer that can upsert compatible fields into `subject`, but the recommended public update path is `tools/archive_update.py` with a staged temporary database.

## Safe Archive update flow

```bash
python tools/archive_update.py --download --url <release.zip>
python tools/archive_update.py --extract
python tools/archive_update.py --create-temp-db --temp-db chronoshelter_archive_tmp
python tools/archive_update.py --validate --temp-db chronoshelter_archive_tmp
python tools/archive_update.py --plan-swap --temp-db chronoshelter_archive_tmp
```

The Archive updater never touches `my_collection`.
