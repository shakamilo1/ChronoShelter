# ChronoShelter

ChronoShelter 是一个本地 Bangumi 动画资料库 MVP。它读取 Bangumi `subject.jsonlines`，融合可选的 `bangumi-data/dist/data.json`，将动画条目安全导入 MySQL，并通过 FastAPI + Jinja2 模板提供动画列表、搜索和详情页。

## 完整项目结构

```text
ChronoShelter/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ models.py
│  │  ├─ repositories.py
│  │  ├─ routers/
│  │  │  ├─ anime.py
│  │  │  └─ health.py
│  │  ├─ templates/
│  │  │  ├─ base.html
│  │  │  ├─ index.html
│  │  │  └─ anime_detail.html
│  │  └─ static/style.css
│  └─ requirements.txt
├─ importer/
│  ├─ import_subject_jsonlines.py
│  ├─ bangumi_data_sync.py
│  ├─ merge_engine.py
│  ├─ image_cache.py
│  ├─ infobox_parser.py
│  ├─ normalizer.py
│  └─ README.md
├─ sql/
│  ├─ schema.sql
│  └─ migrations/001_add_sync_columns.sql
├─ tests/
├─ data/              # 本地 bangumi-data 缓存，gitignore
├─ media/covers/      # 本地封面缓存，gitignore
├─ .env.example
├─ README.md
└─ .gitignore
```

## 数据流架构图

```text
Bangumi subject.jsonlines ─┐
                           ├─ importer/merge_engine.py ── UnifiedAnimeModel ── safe UPSERT ── MySQL bangumi_anime
bangumi-data data.json ────┘              │
                                          └─ image_cache.py ── media/covers/{anime_id}.jpg

FastAPI/Jinja2 ── repositories.py ── MySQL ── 列表 / 搜索 / 详情页
```

- Bangumi API subject 优先提供 `infobox`、`tags`、`summary`、评分和图片 URL。
- bangumi-data 优先提供更结构化的首播时间 `air_date` 和 `broadcast`。
- 所有数据库写入都必须经过 merge layer，bangumi-data 同步本身绝不直接写主数据库。

## 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
```

## 配置 .env

复制示例配置，不要把真实密码提交到 Git：

```bash
cp .env.example .env
```

按本地 MySQL 修改：

```dotenv
CHRONOSHELTER_DB_HOST=127.0.0.1
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_DB_NAME=chronoshelter
```

## 初始化或迁移数据库

首次初始化：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS chronoshelter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p chronoshelter < sql/schema.sql
```

已有 ChronoShelter v1 数据库时，不要 drop/truncate/rebuild 表，只运行增量迁移：

```bash
mysql -u root -p chronoshelter < sql/migrations/001_add_sync_columns.sql
```

## 如何同步 bangumi-data

自动下载最新 `data.json`：

```bash
python importer/bangumi_data_sync.py --download
```

检查远端是否有更新但不替换本地文件：

```bash
python importer/bangumi_data_sync.py --check-update
```

用户手动下载或替换 `data.json`：

```bash
python importer/bangumi_data_sync.py --file ./data.json
```

同步结果保存到 `data/bangumi_data.json`；如果本地已有文件，会先复制一份到 `data/backups/`。该同步步骤只维护本地 JSON 文件，不会写 MySQL。

## 如何保护旧数据库

ChronoShelter 遵守以下规则：

- 永不执行 `DROP TABLE`、`TRUNCATE` 或重建已有表。
- schema 使用 `CREATE TABLE IF NOT EXISTS`；迁移只做 `ADD COLUMN IF NOT EXISTS`。
- 导入使用 `INSERT ... ON DUPLICATE KEY UPDATE`。
- 开启 `--safe-mode` 后，只填充缺失字段；已有 `name_cn`、`name_en`、`infobox`、图片、日期、摘要等字段不会被覆盖。
- 远端为空值时不会覆盖本地有效值。

## 如何运行 importer

试跑 100 条，不写数据库：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100 --dry-run
```

融合本地 bangumi-data，并用 safe-mode 保护旧数据：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --bangumi-data data/bangumi_data.json --safe-mode
```

调试单个 Bangumi 条目：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --bangumi-data data/bangumi_data.json --safe-mode --dry-run
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --bangumi-data data/bangumi_data.json --safe-mode
```

如需在导入时顺便缓存封面，可以显式加 `--cache-covers`。默认不下载图片，避免 3 万+ 条导入时被网络 I/O 阻塞。

## 图片缓存机制

- 封面缓存模块为 `importer/image_cache.py`。
- 本地保存路径为 `media/covers/{anime_id}.jpg`。
- 数据库保存 `cover_local_path`，页面优先展示本地缓存；没有缓存时回退到远端 URL。
- 缓存按 `anime_id` 去重，文件已存在时不会重复下载。
- 默认 lazy 策略：导入不下载图片；需要时再用 `--cache-covers` 或后续任务触发下载。

## 启动网站

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

打开：

- 首页：http://127.0.0.1:8000/
- 健康检查：http://127.0.0.1:8000/health
- 详情页：http://127.0.0.1:8000/anime/285757

## 如何验证数据正确性

1. `python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --bangumi-data data/bangumi_data.json --safe-mode --dry-run`，确认输出 `imported=1 skipped=0 errors=0`。
2. 执行正式导入后，用 SQL 检查关键字段：
   ```sql
   SELECT id, name_cn, name_en, air_date, air_year, air_month, broadcast, eps FROM bangumi_anime WHERE id = 285757;
   ```
3. 打开详情页，确认标题、集数、评分、Infobox、tags、meta_tags 正常展示。
4. 对已有旧数据重复导入并加 `--safe-mode`，确认原有非空字段没有被覆盖。

## 常见问题

### Windows 控制台乱码

请使用 UTF-8 控制台：

```powershell
chcp 65001
$env:PYTHONUTF8=1
```

### 数据库连接失败

检查 `.env` 中的 host、port、user、password、database 是否正确；确认 MySQL 服务已启动；确认已执行 `sql/schema.sql` 或增量迁移。

### name_en 为什么不会显示 TV？

Bangumi 的 `meta_tags` 或别名中可能出现 `TV`、`漫画改` 等分类词。ChronoShelter 的 normalizer 只接受 ASCII 且包含英文字母的英文标题候选，并过滤 `TV` 等非标题值；详情页也会防止把 `TV` 当英文标题展示。

## 后续增强方向

- 独立封面下载队列和失败重试。
- 分页、排序和高级筛选。
- SQLAlchemy/Alembic 迁移管理。
- 后台导入任务和导入日志页面。
- Docker Compose 一键启动 MySQL + Web。
