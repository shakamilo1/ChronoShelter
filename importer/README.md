# Bangumi 导入器

## 同步 bangumi-data

```bash
python importer/bangumi_data_sync.py --download
python importer/bangumi_data_sync.py --check-update
python importer/bangumi_data_sync.py --file ./data.json
```

同步后的原始文件保存在 `data/bangumi_data.json`，已有文件会备份到 `data/backups/`。同步命令不会写入 MySQL。

## 导入 subject.jsonlines

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100 --dry-run
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --bangumi-data data/bangumi_data.json --safe-mode
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --safe-mode --dry-run
```

默认只导入 Bangumi `type=2` 的动画条目。导入时使用 `ON DUPLICATE KEY UPDATE`。

## safe-mode

`--safe-mode` 用于保护已有数据库：只填充缺失字段，不覆盖已有 `name_cn`、`name_en`、`infobox`、图片、日期、摘要等非空字段。

## 图片缓存

默认不下载图片，避免大批量导入被网络阻塞。需要导入时缓存封面可加：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --cache-covers
```

缓存路径为 `media/covers/{anime_id}.jpg`，已存在文件不会重复下载。
