# Bangumi 导入器

## 先检查已有数据库

```bash
python tools/inspect_schema.py
```

导入器会在写入 `bangumi_anime` 前读取实际字段，只写存在的列。缺少可选新字段时会提示需要执行哪个 migration，不会因为缺少 `cover_local_path`、`sites_json` 等字段直接崩溃。

## 同步 bangumi-data

```bash
python tools/update_bangumi_data.py --download
python tools/update_bangumi_data.py --check
python tools/update_bangumi_data.py --file ./data.json
```

同步后的原始文件保存在 `data/bangumi-data/data.json`，已有文件会备份到 `data/bangumi-data/backups/`。同步命令不会写入 MySQL。

## 导入 subject.jsonlines

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100 --dry-run
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --bangumi-data data/bangumi-data/data.json --safe-mode
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --safe-mode --dry-run
```

默认只导入 Bangumi `type=2` 的动画条目。导入时使用 `ON DUPLICATE KEY UPDATE`，并且不会写入 `my_collection`。

## safe-mode

`--safe-mode` 用于保护已有数据库：只填充缺失字段，不覆盖已有 `name_cn`、`name_en`、`infobox`、图片、日期、摘要等非空字段。

## 图片缓存

默认不下载图片，避免大批量导入被网络阻塞。推荐使用独立工具：

```bash
python tools/cache_covers.py --missing --limit 100
```
