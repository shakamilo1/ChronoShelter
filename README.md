# ChronoShelter

ChronoShelter 已重构为可直接放入 ASUSTOR Web Center 的 PHP 8.4 网站。运行入口不再依赖 Docker、FastAPI、Uvicorn 或任何 Python Web 服务；Python 仅作为离线导入和维护工具保留。

## 新 PHP 项目结构

```text
ChronoShelter/
├── index.php              # 首页海报墙
├── subject.php            # 动画详情页
├── collection.php         # 我的收藏
├── collection_edit.php    # 收藏编辑页
├── admin.php              # 管理页面
├── config/
│   ├── config-example.php # 唯一示例配置文件
│   └── config.php         # 用户本地配置；不提交 Git
├── includes/
│   ├── database.php       # PDO 工厂与 HTML 转义
│   ├── bangumi.php        # chrono_bangumi 查询
│   ├── collection.php     # chrono_library.collections 读写
│   └── image.php          # 本地封面缓存
├── templates/
│   ├── header.php
│   └── footer.php
├── static/
│   ├── css/
│   ├── js/
│   └── img/
├── covers/                # 本地缓存封面：covers/subjects/{level1}/{level2}/{safe_remote_filename}
├── data/                  # Archive 输入、处理结果与离线日志
├── database/              # 新部署初始化 schema
├── docs/                  # 部署与维护文档
├── importer/              # 离线导入工具，继续保留
├── tools/                 # 离线管理工具，继续保留
└── sql/                   # 数据库结构与迁移 SQL
```

## 首次部署完整流程

从项目根目录 `ChronoShelter/` 操作，不要再创建 `ChronoShelter/ChronoShelter/` 这种嵌套目录。

```bash
git clone <repo-url> ChronoShelter
cd ChronoShelter
cp config/config-example.php config/config.php
# 编辑 config/config.php
```

然后按顺序执行：

1. 修改 `config/config.php` 中的 MariaDB 连接和管理员密码哈希。
2. 创建 `chrono_bangumi` 与 `chrono_library`。
3. 执行 `database/chrono_bangumi_schema.sql` 与 `database/chrono_library_schema.sql`。
4. 将 Bangumi Archive zip 放入 `data/archive/incoming/`，解压/处理到 `data/archive/processed/`。
5. 使用 `python importer/import_archive_dump.py --dir data/archive/processed` 导入公共 Archive 数据。
6. 用 PHP 8.4 / ASUSTOR Web Center 指向项目根目录。
7. 打开网站，跳转登录页后使用 `config/config.php` 中配置的管理员账号登录。

唯一测试目录是项目根目录下的 `tests/`。请从项目根目录运行 `pytest`，避免重复 clone 到子目录导致 `import file mismatch`。


## 从旧版本升级前后

升级旧版本前，先备份本地配置，避免覆盖或误删 NAS 上的真实数据库密码：

```bash
cp config/config.php config/config.php.bak
```

升级后，如果 `config/config.php` 不存在，就从示例配置创建：

```bash
cp config/config-example.php config/config.php
```

然后把备份中的 MariaDB 连接、数据库名、管理员用户名和 `password_hash` 合并回新的 `config/config.php`。

## 数据库设计

公共 Bangumi Archive 数据库：`chrono_bangumi`。

- `subjects`
- `episodes`
- `persons`
- `characters`
- `subject_persons`
- `subject_characters`
- `subject_relations`
- `person_characters`
- `person_relations`

私人收藏数据库：`chrono_library`。

- `collections`
- `cover_cache`

网站只展示 `subjects.type = 2` 的动画数据，暂时忽略音乐、游戏、三次元等其他类型。收藏功能只写入 `chrono_library.collections`。项目不再使用旧库 `chrono_shelter`，也不依赖旧表 `bangumi_anime`。

## 初始化数据库

首次部署需要先创建两个空数据库，然后导入表结构。SQL 文件只包含表结构、索引和必要约束，不包含用户数据、私人收藏或大量动画数据。

```sql
CREATE DATABASE IF NOT EXISTS chrono_bangumi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS chrono_library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
mysql -u root -p chrono_bangumi < database/chrono_bangumi_schema.sql
mysql -u root -p chrono_library < database/chrono_library_schema.sql
```

如果你只需要单独补建索引，也可以分别导入：

```bash
mysql -u root -p chrono_bangumi < sql/create_chrono_bangumi_indexes.sql
mysql -u root -p chrono_library < sql/create_chrono_library_indexes.sql
```


注意：`subjects.name` 与 `subjects.name_cn` 使用 `VARCHAR(512)` + `utf8mb4`。初始化 SQL 中的 `idx_subjects_type_name_name_cn` 已使用 `name(191), name_cn(191)` 前缀索引，以避免 InnoDB 单索引键长度超过 3072 bytes。

Bangumi Archive 数据需要通过 Python importer 离线导入：

```bash
python importer/import_archive_dump.py --dir data/archive/processed --dry-run
python importer/import_archive_dump.py --dir data/archive/processed
python importer/import_archive_dump.py --dir data/archive/processed --batch-size 1000
```

## 数据库用户权限

不要使用 MariaDB root/admin 用户运行网站。建议创建单独用户：

```sql
CREATE USER 'chronoshelter'@'%' IDENTIFIED BY 'change-this-password';

GRANT SELECT
ON chrono_bangumi.*
TO 'chronoshelter'@'%';

GRANT SELECT, INSERT, UPDATE, DELETE
ON chrono_library.*
TO 'chronoshelter'@'%';

FLUSH PRIVILEGES;
```

如果 Web 服务与 MariaDB 在同一台机器，可以把 `'%'` 改为 `'localhost'`。完整部署流程见 [`docs/deployment.md`](docs/deployment.md)。

## 数据库连接配置方法

首次部署先复制 `config/config-example.php` 为 `config/config.php`；PHP 与 Python importer 共享这个本地 `config/config.php`，也可以通过环境变量覆盖：

```bash
CHRONOSHELTER_DB_HOST=127.0.0.1
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_PUBLIC_DB_NAME=chrono_bangumi
CHRONOSHELTER_LIBRARY_DB_NAME=chrono_library
```

在 ASUSTOR 上编辑 `config/config.php`，将用户和密码改为 MariaDB/phpMyAdmin 中创建的账号。该账号需要：

- 对 `chrono_bangumi` 有读取权限。
- 对 `chrono_library.collections` 和 `chrono_library.cover_cache` 有读取、插入、更新权限。

`config/config.php` 不提交 Git；仓库只保留 `config/config-example.php` 作为唯一示例配置。不要新增 `db_config.py`、`database_config.py` 等第二套数据库密码配置；Python importer 会读取同一份本地 `config/config.php`。

## 页面功能

- `index.php`：动画海报墙，显示封面、中文名、日文名、年份、评分，并提供“加入收藏”按钮。
- `subject.php?id=xxx`：动画详情页，显示中文名、日文名、类型、放送日期、话数、简介、标签、评分、收藏人数、制作人员和角色。
- `collection.php`：我的收藏列表。
- `collection_edit.php?id=xxx`：编辑是否收藏、收藏日期、媒体类型、字幕组、来源网站、我的评分、备注和观看进度。
- `admin.php`：显示 subjects 数量、episodes 数量、收藏数量，并预留 Bangumi 数据更新入口。

## 首页分页性能与索引

首页只展示 `subjects.type = 2` 动画，默认按 `date DESC, id DESC` 排序。`list_anime()` 先在内层查询使用 `idx_subjects_type_date_id (type, date, id)` 只读取当前页的 `id,date`，完成 `WHERE type = 2`、排序、`LIMIT/OFFSET` 后，再按主键读取这 50 条完整记录并关联 `cover_cache` 与 `collections`，避免 MariaDB 对全部动画做临时表和 filesort。生产查询不依赖 MariaDB 查询缓存，也不使用 `SQL_NO_CACHE`。

已有部署不需要重建数据库、不需要修改私人收藏数据、不需要修改或重新下载封面，但必须在 `chrono_bangumi` 上执行新增索引迁移：

```bash
mysql -u root -p chrono_bangumi < sql/migrations/004_add_subjects_pagination_indexes.sql
```

保留 `idx_subjects_type_score_id (type, score, id)` 供未来评分排序使用。未来如果增加名称、NSFW 或标签筛选，筛选条件必须进入内层分页查询的 `WHERE`，并让 `count_anime() 使用相同条件`；普通 B-tree 只适合精确/前缀名称搜索（如 `高达%`），不解决 `%高达%` 任意包含搜索。`meta_tags` 是 JSON，不要直接给整段 JSON 建普通索引；如需标签筛选，应拆成 `subject_meta_tags(subject_id, tag)` 并建立 `(tag, subject_id)`。

## 图片缓存

网页请求只读取本地目录中的封面：

```text
covers/subjects/{level1}/{level2}/{subject_id}_{BangumiSuffix}.{ext}
```

本地占位图在 `config/config.php` 中配置：

```php
'covers' => [
    'directory' => dirname(__DIR__) . '/covers',
    'public_path' => 'covers',
    'subjects_directory' => 'subjects',
    'fallback' => 'logo.png',
],
```

页面只显示数据库 `cover_cache.local_path` 指向的本地封面，文件名来自 `images.large` URL 的安全 basename（同一 subject 可能先后出现多个文件名），扩展名由真实图片格式决定并支持 `jpg`、`png`、`webp`，例如 `covers/subjects/000/491/491569_xxxxx.jpg`；条目封面不存在、为空或损坏时立即显示 `covers/logo.png`。如果配置的占位图也不存在，则退回 `static/img/placeholder.svg`。PHP 页面不会访问 Bangumi、不会在渲染期间下载封面，也不会因为外部站点不可达而等待超时。

动画封面只通过 Windows/Python 离线同步工具维护，详见 [`docs/bangumi_cover_sync.md`](docs/bangumi_cover_sync.md)。需要补充条目封面时，应在能够访问 Bangumi 的独立维护环境中运行 `python tools/download_covers.py sync --resume`，再把 `covers/subjects/` 同步到 NAS，并在 NAS 本地准备 `covers/logo.png`；不要从网页请求触发下载。

## 数据目录规范

大量 Archive 文件不要放在项目根目录。统一使用：

```text
data/
├── archive/
│   ├── incoming/      # 放置下载的 archive.zip
│   ├── extracted/     # 解压临时目录
│   └── processed/     # 验证通过、供 importer 导入的 jsonlines
└── logs/              # 离线工具日志
```

## 保留的离线工具

以下目录继续保留，用于手动或未来后台触发的数据维护：

- `importer/`
- `tools/`
- `sql/`

常用命令示例：

```bash
python importer/import_archive_dump.py --dir data/archive/processed --dry-run
python importer/import_archive_dump.py --dir data/archive/processed
python importer/import_archive_dump.py --dir data/archive/processed --batch-size 1000
python tools/archive_update.py --latest
python tools/download_covers.py sync --max-pages=1 --max-items=1 --api-delay=0 --download-delay=0
python importer/bangumi_data_sync.py --help
```

`admin.php` 第一版只提示手动运行 Archive 更新工具；不会从网页启动 Python 后台服务。

## 本地测试方法

语法检查：

```bash
find . -name '*.php' -print0 | xargs -0 -n1 php -l
```

本地临时 PHP 内置服务器（仅用于开发验证，不是部署依赖）：

```bash
php -S 127.0.0.1:8080
```

打开：

```text
http://127.0.0.1:8080/index.php
```

如需连接真实 MariaDB，请先在 `config/config.php` 或环境变量中配置 `chrono_bangumi` 与 `chrono_library`。

## ASUSTOR 部署方法

1. 在 ASUSTOR App Central 安装并启用 Web Center、Nginx、PHP 8.4、MariaDB、phpMyAdmin。
2. 按 [`docs/deployment.md`](docs/deployment.md) 创建 `chrono_bangumi` 与 `chrono_library`，并导入 `database/` 下的 schema。
3. 将整个 `ChronoShelter/` 目录复制到：

   ```text
   /Web/ChronoShelter
   ```

4. 确认 Web Center 的站点根目录指向 `/Web/ChronoShelter`，PHP 版本选择 PHP 8.4。
5. 编辑 `/Web/ChronoShelter/config/config.php`，填写 MariaDB 主机、端口、用户名、密码和数据库名。
6. 确保 Web 服务用户可写入：

   ```text
   /Web/ChronoShelter/covers
   ```

7. 访问 `install_check.php` 检查 PHP、PDO MySQL、MariaDB 连接与必要表。部署完成后建议删除或限制访问该检查页。
8. 通过浏览器访问 Web Center 配置的站点 URL。

## 废弃/删除的运行入口

FastAPI 运行入口已经废弃并从当前应用结构移除：

- `backend/app/`
- `backend/requirements.txt`
- `Dockerfile`
- `docker-compose.yml`

这些不再是 ChronoShelter 的部署方式。

## 登录与安全

ChronoShelter 是私人 NAS 应用，默认启用单用户登录。未登录访问以下页面会自动跳转到 `login.php`：

- `index.php`
- `subject.php`
- `collection.php`
- `collection_edit.php`
- `admin.php`

认证配置位于 `config/config.php`：

```php
'auth' => [
    'enabled' => true,
    'username' => 'admin',
    'password_hash' => '这里填写密码哈希',
],
```

密码不要明文保存。生成密码哈希：

```bash
php -r "echo password_hash('你的密码', PASSWORD_DEFAULT);"
```

然后将输出填入 `password_hash`。也可以通过环境变量覆盖：

```bash
CHRONOSHELTER_AUTH_USERNAME=admin
CHRONOSHELTER_AUTH_PASSWORD_HASH='password_hash 输出值'
```

登录使用 PHP Session。登录成功后会调用 `session_regenerate_id(true)` 更新 Session ID，以降低 session fixation 风险。所有 POST 表单都带有 CSRF Token；校验失败会返回 HTTP 403 并拒绝请求。

## 封面批量下载工具

网页浏览不会联网补齐封面。正式架构是：NAS 只提供共享目录、MariaDB 和网页服务；开启 VPN 的 Windows 维护机运行 Python 同步器并可直接写入 NAS SMB/UNC 共享目录，随后 Windows PHP 连接 NAS MariaDB 执行 `import-mapping`。Python 同步器固定只扫描 Bangumi `type=2` 动画，使用官方 `GET /v0/subjects?type=2&limit=50&offset=...` 批量接口，只读取 `images.large`。对标准 Bangumi `images.large` 文件名，优先将 API URL basename 与 SQLite 中保存的 `remote_filename` 比较；文件名相同且本地文件完整时跳过下载，文件名变化时下载新版，只有异常或不可识别 basename 才退回完整 URL 比较。

安装 Python 依赖：

```bash
python -m pip install -r requirements-dev.txt
```

小规模验证（不会启动完整下载）：

```bash
python tools/download_covers.py sync --max-pages=1 --max-items=1 --api-delay=0 --download-delay=0 --verbose
```

首次全量同步或中断后恢复（仅在得到明确授权后运行）：

```bash
python tools/download_covers.py sync --resume
```

本地严格验证与导出 PHP 可导入的 JSONL 映射：

```bash
python tools/download_covers.py verify-files
python tools/download_covers.py export-mapping --file=var/cover-sync/reports/cover-mapping.jsonl
```

确认 `covers/subjects/` 中新增或更新的文件已经写入 NAS 共享目录后，在 Windows 维护机上用 PHP 连接 NAS MariaDB 导入映射：

```bash
php bin/bangumi_covers.php import-mapping --file=var/cover-sync/reports/cover-mapping.jsonl
```

`BANGUMI_ACCESS_TOKEN` 可选且只会发送给严格匹配的 `https://api.bgm.tv:443` API JSON 请求；图片请求和每一跳重定向都不会携带 Authorization。可用 `CHRONOSHELTER_COVERS_DIR`、`CHRONOSHELTER_COVER_SYNC_STATE_DIR` 指向 NAS 共享目录，并用 `--proxy` 或 `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` 配置代理。NAS 不负责联网下载；Windows Python 负责下载/验证/导出，Windows PHP 负责连接 NAS MariaDB 执行 `import-mapping`。完整说明见 [`docs/bangumi_cover_sync.md`](docs/bangumi_cover_sync.md)。

### 封面清理安全规则

同步程序不会在新封面下载成功、SQLite 更新、MariaDB 写入或 import-mapping 时自动删除旧封面。SQLite 中旧的 `status` 列仅作兼容摘要，新的运行逻辑使用 `artifact_status` 表示最后成功文件是否可用、`deploy_status` 表示 `deployed`/`pending_deploy`/`mapping_failed`，以及 `last_check_result` 记录 `unchanged`、`updated`、`remote_missing`、`http_failed`、`local_invalid` 等最近检查结果。失败的 `pending_update`、`failed`、`mapping_failed`、`remote_missing` 不会污染网站当前 `cached` 映射；只要旧文件仍有效，export-mapping 会继续导出旧封面。本 PR 不提供实际封面删除命令；旧文件在确认不再被生产 `cover_cache` 或可信映射引用前必须保留。

### Windows Python 封面同步

正式架构为 NAS 只提供共享目录、MariaDB 和网页服务；Windows 维护机在 VPN 下运行 `python tools/download_covers.py` 下载/验证/导出，并使用 Windows PHP 连接 NAS MariaDB 执行导入。可用 `CHRONOSHELTER_COVERS_DIR` 指向 NAS SMB/UNC 封面目录，`CHRONOSHELTER_COVER_SYNC_STATE_DIR` 指向 NAS 共享中的非公开同步状态目录；Python 同步器不会连接 MariaDB。常用命令：

```powershell
python tools/download_covers.py sync --resume
python tools/download_covers.py verify-files
python tools/download_covers.py export-mapping --file var/cover-sync/reports/cover-mapping.jsonl
```

随后确认封面文件已经写入 NAS 共享目录，再在 Windows 维护机上运行 `php bin/bangumi_covers.php import-mapping --file=var/cover-sync/reports/cover-mapping.jsonl`，由 Windows PHP 连接 NAS MariaDB 写入映射。默认命令不带代理；只有确实使用本地 HTTP 代理时才添加 `--proxy <代理地址>`，也可使用 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 环境变量。
