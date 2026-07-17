# ChronoShelter

ChronoShelter 当前数据层拆分为两个 MariaDB 数据库：

1. `chrono_bangumi`：公共 Bangumi Archive 数据，可定期完全重建。
2. `chrono_library`：用户个人收藏，永久保存，不随 Archive 更新。

本 PR 只生成可人工审阅的 `CREATE TABLE` / 索引 SQL 文件；不会连接 MariaDB、不会执行 SQL、不会创建数据库、不会修改旧 `chrono_shelter`。

## 公共数据库：chrono_bangumi

不要继续使用 `bangumi_anime`，也不要设计 `anime` 表。公共数据按照 Bangumi Archive 原始实体模型读取：

```text
subjects
episodes
persons
characters
subject_persons
subject_characters
subject_relations
person_characters
person_relations
```

## 用户数据库：chrono_library

原 `my_collection` 迁移目标为 `collections`，只保存用户信息：

- `subject_id`
- 收藏状态
- 收藏日期
- 媒介类型
- 字幕组
- 来源网站
- 我的评分
- 备注
- 观看进度
- 扩展 JSON

收藏功能只写 `chrono_library.collections`。

## 新数据流

```text
chrono_bangumi.subjects(type=2)
  └─ 海报墙 / 搜索

chrono_bangumi.subjects
  + episodes
  + persons via subject_persons
  + characters via subject_characters
  + chrono_library.collections
  └─ 动画详情页

一键收藏 / 编辑收藏
  └─ 只 INSERT/UPDATE chrono_library.collections

Archive 更新
  └─ 下载 release zip -> 解压 -> import_archive_dump.py 导入临时公共库 -> 验证 -> 人工计划替换 chrono_bangumi 公共表
     不直接覆盖生产库，不触碰 chrono_library.collections
```

## 配置

```bash
cp .env.example .env
```

```dotenv
CHRONOSHELTER_DB_HOST=host.docker.internal
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_PUBLIC_DB_NAME=chrono_bangumi
CHRONOSHELTER_LIBRARY_DB_NAME=chrono_library
```

## 接入已有数据库

只读检查：

```bash
python tools/inspect_schema.py
```

备份个人库：

```bash
mkdir -p backups
mysqldump --single-transaction -u root -p chrono_library collections > backups/collections_before_change.sql
```

然后再根据 `sql/` 下的初始化 SQL 和下面的 migration SQL 草稿人工评估，不要在未确认字段结构前执行。

## Archive dump 导入器

从 Archive dump 目录读取 jsonlines 文件并写入 `chrono_bangumi` 已存在表（不创建数据库/表）：

```bash
python importer/import_archive_dump.py --dir /path/to/archive-dump --dry-run
python importer/import_archive_dump.py --dir /path/to/archive-dump --table subjects --limit 100
python importer/import_archive_dump.py --dir /path/to/archive-dump
```

支持的文件名包括 `subject.jsonlines`、`episode.jsonlines`、`person.jsonlines`、`character.jsonlines`、`subject-persons.jsonlines`、`subject-characters.jsonlines`、`subject-relations.jsonlines`、`person-characters.jsonlines`、`person-relations.jsonlines`。

## Archive 更新工具

普通用户不需要手动解压。`tools/archive_update.py` 负责准备本地 Archive 目录，但不负责导入数据库：

```bash
# 使用本地 release zip
python tools/archive_update.py --file archive.zip

# 或下载 release zip 到 data/archive/downloads/ 后自动解压
python tools/archive_update.py --url <bangumi-archive-release.zip-url>

# 预留：未来可从 latest.json 自动发现最新版
python tools/archive_update.py --latest
```

自动流程：

```text
release zip / release URL
  -> data/archive/downloads/
  -> data/archive/current_tmp/
  -> 检查 required jsonlines
  -> rename/copy 为 data/archive/current/
```

验证成功后再导入：

```bash
python importer/import_archive_dump.py --dir data/archive/current --dry-run
python importer/import_archive_dump.py --dir data/archive/current
```

## 图片缓存

不依赖 Archive 图片字段。封面通过 Bangumi API 获取：`GET https://api.bgm.tv/v0/subjects/{subject_id}/image?type=large`，保存到 `media/covers/{subject_id}.jpg`。下载时会检查 HTTP 状态、`Content-Type`、文件大小和图片尺寸，并拒绝 `https://lain.bgm.tv/img/no_icon_subject.png`。

```bash
python tools/cache_covers.py --missing
python tools/cache_covers.py --id 285757
python tools/cache_covers.py --missing --limit 100
python tools/cache_covers.py --all
python tools/cache_covers.py --retry-failed
```

如果 `chrono_library.cover_cache` 表存在，工具会记录 `status`、`local_path`、`error`、`http_status`、`content_type`、`file_size`、`width`、`height`。失败日志仍写入 `logs/cover_failures.log`。

## 网站查询逻辑

- 海报墙：`subjects(type=2)`。
- 详情页：`subjects + episodes + persons + characters + collections`。
- 一键收藏：只写 `collections`。
- 编辑收藏：只写 `collections`。

## 启动

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8700
```

Docker / NAS：

```bash
mkdir -p media/covers data/archive
cp .env.example .env
docker compose up -d --build
```

## 数据库初始化 SQL（只生成，不自动执行）

本仓库现在提供三个手动执行用 SQL 文件：

- `sql/create_chrono_bangumi_tables.sql`：仅包含 `CREATE TABLE`，用于已手动选择的 `chrono_bangumi`，字段按官方 Bangumi Archive README 模型校正。
- `sql/create_chrono_library_tables.sql`：仅包含 `CREATE TABLE`，用于已手动选择的 `chrono_library.collections` 和可选 `cover_cache`；`collections` 只保存个人收藏字段，不包含 `name`、`summary`、`tags`、`image`、`infobox` 等公共字段。
- `sql/create_indexes.sql`：为海报墙、搜索、详情页关联查询、封面缓存状态查询创建推荐索引。

这些 SQL 文件不会被应用自动执行；表结构 SQL 已删除 `CREATE DATABASE` / `USE`，需要你手动选择目标库后执行；旧库 `chrono_shelter`、旧表 `bangumi_anime`、旧表 `my_collection` 都不会被本 PR 修改。

## Migration SQL 草稿（不要直接执行）

下面仅是人工迁移参考，必须先 `inspect_schema.py` 和备份。

```sql
-- If migrating from my_collection, copy data manually after checking columns.
-- CREATE TABLE chrono_library.collections LIKE old_db.my_collection;
-- INSERT INTO chrono_library.collections SELECT * FROM old_db.my_collection;

-- Add only nullable columns after confirming they do not already exist:
-- ALTER TABLE chrono_library.collections ADD COLUMN subject_id INT UNSIGNED NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN collected BOOLEAN NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN collection_date DATE NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN media_type VARCHAR(128) NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN subtitle_group VARCHAR(255) NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN source_site VARCHAR(255) NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN my_rating FLOAT NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN notes TEXT NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN progress VARCHAR(128) NULL;
-- ALTER TABLE chrono_library.collections ADD COLUMN extra_json JSON NULL;

-- Optional cover cache status table (manual draft):
-- CREATE TABLE chrono_library.cover_cache (
--   subject_id INT UNSIGNED PRIMARY KEY,
--   status VARCHAR(32) NULL,
--   local_path TEXT NULL,
--   error TEXT NULL,
--   http_status INT NULL,
--   content_type VARCHAR(255) NULL,
--   file_size INT UNSIGNED NULL,
--   width INT NULL,
--   height INT NULL,
--   updated_at DATETIME NULL
-- );
```

公共库 `chrono_bangumi` 应由 Bangumi Archive 导入到临时库并验证后替换，不能在 Web 运行时直接覆盖生产库。
