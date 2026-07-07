# ChronoShelter

ChronoShelter 是“公共番剧资料库 + 个人收藏系统”。公共资料保存在 `bangumi_anime`，个人收藏保存在 `my_collection`；导入、迁移和更新默认以保护现有数据为第一优先级。

## 完整项目结构

```text
ChronoShelter/
├─ backend/app/              # FastAPI + Jinja2 网站
│  ├─ routers/anime.py       # 海报墙、详情、收藏、编辑收藏
│  ├─ templates/             # base/index/detail/collection_edit
│  └─ static/                # CSS 与默认占位图
├─ importer/                 # subject.jsonlines、bangumi-data、merge、图片缓存核心逻辑
├─ tools/
│  ├─ update_bangumi_data.py # data.json 下载/检查/替换
│  └─ cache_covers.py        # 本地海报缓存命令
├─ sql/
│  ├─ schema.sql             # 首次初始化 schema
│  └─ migrations/            # 只做安全增量迁移
├─ data/bangumi-data/        # data.json 挂载目录，gitignore
├─ media/covers/             # 本地海报挂载目录，gitignore
├─ docker-compose.yml
├─ Dockerfile
├─ .env.example
└─ README.md
```

## 数据流架构图

```text
subject.jsonlines ─┐
                   ├─ merge_engine.py ── UnifiedAnimeModel ── safe UPSERT ── bangumi_anime ── 海报墙/详情/搜索
bangumi-data ──────┘         │                                      │
                             └─ sites/broadcast/time                │
                                                                    ├─ my_collection ── 收藏状态/评分/备注
cache_covers.py ── image_cache.py ── media/covers/{bangumi_id}.jpg ─┘
```

## 数据库定位

- `bangumi_anime`：公共 Bangumi 动画资料库，支持从 `subject.jsonlines` 全量导入，也支持从 bangumi-data 更新放送时间、broadcast、站点信息。禁止直接删除。
- `my_collection`：用户个人收藏数据，绝对不能丢，保存收藏状态、收藏日期、媒介类型、字幕组、来源网站、我的评分、备注和其他信息。

## 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 配置 .env / MariaDB

```bash
cp .env.example .env
```

NAS / Docker 场景推荐让容器连接宿主机 MariaDB：

```dotenv
CHRONOSHELTER_DB_HOST=host.docker.internal
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_DB_NAME=chronoshelter
```


## 接入已有数据库

不要假设 MariaDB 是全新结构。推荐流程：

```bash
python tools/inspect_schema.py
mkdir -p backups
mysqldump --single-transaction -u root -p chronoshelter bangumi_anime my_collection > backups/chronoshelter_before_migration.sql
mysql -u root -p chronoshelter < sql/migrations/001_add_sync_columns.sql
mysql -u root -p chronoshelter < sql/migrations/002_safe_my_collection_and_cover_cache.sql
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8700
python tools/cache_covers.py --missing --limit 100
```

`tools/inspect_schema.py` 是只读工具，会输出 `bangumi_anime` 和 `my_collection` 的字段列表与行数。当前程序期望字段、旧字段兼容关系和 migration 优先级见 `docs/current_schema.md`。

`my_collection` 通过 `backend/app/collection_mapper.py` 做字段映射，兼容 `collection_date/collect_date/created_at/date`、`notes/note/remark`、`my_rating/rating`、`collected/is_collected` 等旧字段名。

## 初始化或安全迁移数据库

首次初始化：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS chronoshelter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p chronoshelter < sql/schema.sql
```

已有旧库时必须先 inspect，再备份，再迁移：

```bash
python tools/inspect_schema.py
mkdir -p backups
mysqldump --single-transaction -u root -p chronoshelter bangumi_anime my_collection > backups/chronoshelter_before_migration.sql
mysql -u root -p chronoshelter < sql/migrations/001_add_sync_columns.sql
mysql -u root -p chronoshelter < sql/migrations/002_safe_my_collection_and_cover_cache.sql
```

迁移原则：不 `DROP my_collection`，不 `TRUNCATE my_collection`，不重建已有 `my_collection`，不改变原字段含义，不清空收藏数据，不覆盖已有收藏备注和个人评分；已有表只通过 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 添加可空字段。如果要回滚，先停止 Web，再用 `backups/chronoshelter_before_migration.sql` 恢复。

## NAS 部署

```bash
mkdir -p media/covers data/bangumi-data
cp .env.example .env
# 修改 .env 中 MariaDB 用户、密码、数据库名
docker compose up -d --build
```

- Web 端口：`8700`
- 静态图片路径：`/media/covers/`
- 图片挂载：`./media/covers:/app/media/covers`
- bangumi-data 挂载：`./data/bangumi-data:/app/data/bangumi-data`

如果 MariaDB 不在宿主机，请把 `.env` 中的 `CHRONOSHELTER_DB_HOST` 改成 NAS 上 MariaDB 的实际地址。

## 更新 bangumi-data

数据源使用 raw URL：`https://raw.githubusercontent.com/bangumi-data/bangumi-data/master/dist/data.json`。

```bash
python tools/update_bangumi_data.py --check
python tools/update_bangumi_data.py --download
python tools/update_bangumi_data.py --file ./data.json
```

文件保存到 `data/bangumi-data/data.json`。更新前会备份旧文件到 `data/bangumi-data/backups/data_YYYYMMDD_HHMMSS.json`。该操作不写 `bangumi_anime`，也绝不写 `my_collection`。

## 导入或更新 bangumi_anime

试跑：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100 --dry-run
```

安全导入并融合 bangumi-data：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --bangumi-data data/bangumi-data/data.json --safe-mode
```

单条调试：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --bangumi-data data/bangumi-data/data.json --safe-mode --dry-run
```

`--safe-mode` 只填补缺失字段，不用空值覆盖有效值，不覆盖 `my_collection`。

## 图片缓存

页面不直接强依赖远程图片：有本地缓存显示本地海报；无缓存显示默认占位图。后台用命令缓存图片：

```bash
python tools/cache_covers.py --missing
python tools/cache_covers.py --all
python tools/cache_covers.py --id 285757
python tools/cache_covers.py --missing --limit 100
```

缓存路径：`media/covers/{bangumi_id}.jpg`。命令有进度条，会跳过已存在文件，失败记录写入 `logs/cover_failures.log`，可断点式重复运行。

## 启动网站

本地：

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8700
```

Docker / NAS：

```bash
docker compose up -d
```

访问：`http://<NAS-IP>:8700/`。

## 如何验证一键收藏

1. 打开海报墙 `/`。
2. 找到未收藏卡片，点击“一键收藏”。
3. 页面返回后按钮变成“已收藏”。
4. SQL 验证：
   ```sql
   SELECT bangumi_id, collected, collection_date FROM my_collection WHERE bangumi_id = 285757;
   ```

## 如何验证详情页

1. 打开 `/anime/285757`。
2. 确认公共字段：标题、日文名、英文名、海报、首播时间、年份/月/星期、集数、官方评分、简介、tags、meta_tags、infobox。
3. 确认个人字段：收藏状态、收藏日期、我的评分、字幕组、来源网站、备注。
4. 点击“编辑收藏”，修改字段并回车保存，返回详情页后确认更新。

## 导入旧 my_collection

如果旧表结构不同，请先导出：

```bash
mysqldump --single-transaction -u root -p chronoshelter my_collection > backups/my_collection_legacy.sql
```

然后根据旧字段映射插入新结构。示例：

```sql
INSERT INTO my_collection (bangumi_id, collected, collection_date, media_type, subtitle_group, source_site, my_rating, notes, extra_json)
SELECT bangumi_id, collected, collection_date, media_type, subtitle_group, source_site, my_rating, notes, extra_json
FROM my_collection_legacy_backup
ON DUPLICATE KEY UPDATE
  collected = my_collection.collected,
  collection_date = COALESCE(my_collection.collection_date, VALUES(collection_date)),
  my_rating = COALESCE(my_collection.my_rating, VALUES(my_rating)),
  notes = COALESCE(my_collection.notes, VALUES(notes));
```

该示例保留已有备注和个人评分优先。
