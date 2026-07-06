# Bangumi 导入器

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --dry-run
```

默认只导入 Bangumi `type=2` 的动画条目。导入时使用 `ON DUPLICATE KEY UPDATE`，并通过 `COALESCE(NULLIF(...))` 避免空值覆盖已有有效值。
