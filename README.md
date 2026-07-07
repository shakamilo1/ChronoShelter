# ChronoShelter

ChronoShelter 是“Bangumi Archive 公共资料库 + 个人收藏系统”。公共数据使用 Archive 原始实体模型，个人收藏保存在 `my_collection`，两者通过 `subject_id`（或旧字段 `bangumi_id`/`anime_id`）关联。

## 数据层设计

禁止新建 `bangumi_anime`。公共库使用 Archive 表：

```text
subject
episode
person
character
subject_person
subject_character
subject_relation
person_character
person_relation
```

公共 Archive 表允许通过 release 定期完全重建；`my_collection` 是个人数据，绝不随 Archive 更新重建、清空或覆盖。

## 数据流

```text
Bangumi Archive release zip
  └─ tools/archive_update.py
      ├─ 下载 release zip
      ├─ 解压
      ├─ 导入临时数据库（人工/后续导入器）
      ├─ 验证 Archive 表
      └─ 计划替换公共表（不直接覆盖生产库）

subject(type=2) ── 海报墙 / 搜索
subject + episode + person + character + my_collection ── 详情页
my_collection ── 一键收藏 / 编辑收藏（唯一会被收藏功能修改的表）
```

## 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## 配置 MariaDB

```bash
cp .env.example .env
```

NAS / Docker 场景推荐：

```dotenv
CHRONOSHELTER_DB_HOST=host.docker.internal
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_DB_NAME=chronoshelter
```

## 接入已有数据库

先只读检查，确认是否已有 Archive 表和个人收藏字段：

```bash
python tools/inspect_schema.py
```

然后备份个人数据：

```bash
mkdir -p backups
mysqldump --single-transaction -u root -p chronoshelter my_collection > backups/my_collection_before_archive.sql
```

如需给个人收藏表补充兼容字段，只运行安全 migration：

```bash
mysql -u root -p chronoshelter < sql/migrations/002_safe_my_collection_and_cover_cache.sql
```

迁移原则：不 drop、不 truncate、不重建 `my_collection`，只添加可空字段。字段兼容说明见 `docs/current_schema.md`。

## 初始化全新数据库

全新部署可创建 Archive 公共表和个人表：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS chronoshelter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p chronoshelter < sql/schema.sql
```

## Archive 更新工具

`tools/archive_update.py` 提供安全流程骨架，不直接覆盖生产库：

```bash
python tools/archive_update.py --download --url <bangumi-archive-release.zip-url>
python tools/archive_update.py --extract
python tools/archive_update.py --create-temp-db --temp-db chronoshelter_archive_tmp
# 将解压后的 Archive 数据导入临时库后：
python tools/archive_update.py --validate --temp-db chronoshelter_archive_tmp
python tools/archive_update.py --plan-swap --temp-db chronoshelter_archive_tmp
```

替换公共库必须在验证临时库后、维护窗口中执行；`my_collection` 不属于 Archive 表，不能被 swap/rebuild。

## 网站功能

- 列表页查询 `subject(type=2)`。
- 详情页展示 `subject`、`episode`、`person`、`character` 和 `my_collection`。
- 一键收藏只修改 `my_collection`。
- 收藏编辑只修改 `my_collection`。
- 字段映射层兼容旧收藏字段：`subject_id/bangumi_id/anime_id`、`collection_date/collect_date/date`、`notes/note/remark`、`my_rating/rating`。

## 图片缓存

Archive 的 `subject.images` 保留远程 URL；页面默认显示本地占位图，后台缓存图片：

```bash
python tools/cache_covers.py --missing
python tools/cache_covers.py --id 285757
python tools/cache_covers.py --missing --limit 100
```

缓存路径：`media/covers/{subject_id}.jpg`。失败日志写入 `logs/cover_failures.log`，可重复运行继续缓存。

## 启动网站

本地：

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8700
```

Docker / NAS：

```bash
mkdir -p media/covers data/archive
cp .env.example .env
docker compose up -d --build
```

访问：`http://<NAS-IP>:8700/`。

## 验证

1. `python tools/inspect_schema.py` 确认 `subject` 与 `my_collection` 存在。
2. 打开 `/`，海报墙应显示 `subject(type=2)`。
3. 点击“一键收藏”，只应新增或更新 `my_collection`。
4. 打开 `/anime/{subject_id}`，详情页应显示 subject、episode、person、character、collection 信息。
5. 运行 `python tools/archive_update.py --validate --temp-db chronoshelter_archive_tmp` 验证临时 Archive 库后，再人工计划公共表替换。
