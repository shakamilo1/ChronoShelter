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
│   └── config.php         # PDO 数据库连接配置
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
├── covers/                # 本地缓存封面：covers/{subject_id}.jpg
├── database/              # 新部署初始化 schema
├── docs/                  # 部署与维护文档
├── importer/              # 离线导入工具，继续保留
├── tools/                 # 离线管理工具，继续保留
└── sql/                   # 数据库结构与迁移 SQL
```

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

Bangumi Archive 数据需要通过 Python importer 离线导入：

```bash
python importer/import_archive_dump.py --dir data/archive/current --dry-run
python importer/import_archive_dump.py --dir data/archive/current
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

默认配置在 `config/config.php`，也可以通过环境变量覆盖：

```bash
CHRONOSHELTER_DB_HOST=127.0.0.1
CHRONOSHELTER_DB_PORT=3306
CHRONOSHELTER_DB_USER=chronoshelter
CHRONOSHELTER_DB_PASSWORD=change-me
CHRONOSHELTER_PUBLIC_DB_NAME=chrono_bangumi
CHRONOSHELTER_LIBRARY_DB_NAME=chrono_library
```

在 ASUSTOR 上可以直接编辑 `config/config.php`，将用户和密码改为 MariaDB/phpMyAdmin 中创建的账号。该账号需要：

- 对 `chrono_bangumi` 有读取权限。
- 对 `chrono_library.collections` 和 `chrono_library.cover_cache` 有读取、插入、更新权限。

## 页面功能

- `index.php`：动画海报墙，显示封面、中文名、日文名、年份、评分，并提供“加入收藏”按钮。
- `subject.php?id=xxx`：动画详情页，显示中文名、日文名、类型、放送日期、话数、简介、标签、评分、收藏人数、制作人员和角色。
- `collection.php`：我的收藏列表。
- `collection_edit.php?id=xxx`：编辑是否收藏、收藏日期、媒体类型、字幕组、来源网站、我的评分、备注和观看进度。
- `admin.php`：显示 subjects 数量、episodes 数量、收藏数量，并预留 Bangumi 数据更新入口。

## 图片缓存

封面缓存使用本地目录：

```text
covers/{subject_id}.jpg
```

图片来源：

```text
https://api.bgm.tv/v0/subjects/{id}/image?type=large
```

下载时会拒绝 Bangumi 的无图占位地址：

```text
https://lain.bgm.tv/img/no_icon_subject.png
```

如果 `chrono_library.cover_cache` 可用，缓存状态会记录在该表中。

## 保留的离线工具

以下目录继续保留，用于手动或未来后台触发的数据维护：

- `importer/`
- `tools/`
- `sql/`

常用命令示例：

```bash
python importer/import_archive_dump.py --dir data/archive/current --dry-run
python importer/import_archive_dump.py --dir data/archive/current
python tools/archive_update.py --latest
python tools/cache_covers.py --missing --limit 100
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

网页浏览时仍会尝试少量补齐缺失封面；大批量下载请使用离线 Python 工具：

```bash
python tools/download_covers.py --missing
```

限制数量：

```bash
python tools/download_covers.py --missing --limit 500
```

降低下载速度、避免给 Bangumi API 造成压力：

```bash
python tools/download_covers.py --missing --delay 10
```

默认延迟为 3 秒。工具查询 `chrono_bangumi.subjects(type=2)`，跳过已有 `chrono_library.cover_cache` 记录或本地已有 `covers/{subject_id}.jpg` 的条目，将封面保存到 `covers/`。运行时可按 `Ctrl+C` 安全停止；已经成功下载的图片会保留，下次运行会自动跳过并继续。失败日志写入：

```text
logs/cover_download.log
```

该工具需要 PyMySQL 和 Pillow：

```bash
python -m pip install PyMySQL Pillow
```

其中：

- PyMySQL 用于连接 MariaDB。
- Pillow 用于验证图片完整性。
