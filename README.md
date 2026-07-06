# ChronoShelter

ChronoShelter 是一个本地 Bangumi 动画资料库 MVP。它读取 Bangumi `subject.jsonlines`，将动画条目导入 MySQL，并通过 FastAPI + Jinja2 模板提供动画列表、搜索和详情页。

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

## 初始化数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS chronoshelter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p chronoshelter < sql/schema.sql
```

如果使用专门用户，请先在 MySQL 中授权该用户访问 `chronoshelter` 数据库。

## 导入 subject.jsonlines

试跑 100 条：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100 --dry-run
```

正式导入：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --limit 100
```

调试单个 Bangumi 条目：

```bash
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757 --dry-run
python importer/import_subject_jsonlines.py --file /path/to/subject.jsonlines --id 285757
```

## 启动网站

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

打开：

- 首页：http://127.0.0.1:8000/
- 健康检查：http://127.0.0.1:8000/health
- 详情页：http://127.0.0.1:8000/anime/285757

## 常见问题

### Windows 控制台乱码

请使用 UTF-8 控制台：

```powershell
chcp 65001
$env:PYTHONUTF8=1
```

### 数据库连接失败

检查 `.env` 中的 host、port、user、password、database 是否正确；确认 MySQL 服务已启动；确认已执行 `sql/schema.sql`。

### name_en 为什么不会显示 TV？

Bangumi 的 `meta_tags` 或别名中可能出现 `TV`、`漫画改` 等分类词。ChronoShelter 的 normalizer 只接受 ASCII 且包含英文字母的英文标题候选，并过滤 `TV` 等非标题值；详情页也会防止把 `TV` 当英文标题展示。

## 后续增强方向

- 分页、排序和高级筛选。
- SQLAlchemy/Alembic 迁移管理。
- 后台导入任务和导入日志页面。
- 更完整的 Bangumi 字段映射。
- Docker Compose 一键启动 MySQL + Web。
