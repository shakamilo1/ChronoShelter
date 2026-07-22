# ChronoShelter 部署指南

本文档面向全新部署。示例中的地址、域名和路径均为占位符，请替换为你自己的环境值，例如 `your-nas-ip`、`example.com`、`/path/to/ChronoShelter`。

## 1. 环境要求

- ASUSTOR Web Center
- Nginx 或 Web Center 支持的 Web Server
- PHP >= 8.4
- PHP 扩展：PDO、PDO MySQL (`pdo_mysql`)
- MariaDB >= 10.x
- phpMyAdmin 或 MariaDB 命令行客户端
- 可选：Python 3.11+，用于离线导入 Bangumi Archive 与批量下载封面

## 2. 上传网站文件

将仓库目录上传到 Web Center 站点目录，例如：

```text
/Web/ChronoShelter
```

或者在通用环境中放到：

```text
/path/to/ChronoShelter
```

确保 Web 服务用户可以写入：

```text
/Web/ChronoShelter/covers
```

项目根目录就是 `ChronoShelter/`。所有 Python 工具、SQL 和测试都从这个目录运行；不要把仓库 clone 成 `ChronoShelter/ChronoShelter/`。

进入项目根目录并编辑唯一配置文件：

```bash
cd /Web/ChronoShelter
cp config/config-example.php config/config.php
# 编辑 config/config.php
```

唯一测试目录是项目根目录下的 `tests/`，`pytest.ini` 也位于项目根目录。请从 `ChronoShelter/` 运行 `pytest`，避免重复 clone 到子目录导致 `import file mismatch`。


## 3. 从旧版本升级前后

升级旧版本前，先备份本地配置：

```bash
cp config/config.php config/config.php.bak
```

升级后，如果 `config/config.php` 不存在，就从示例配置创建：

```bash
cp config/config-example.php config/config.php
```

然后把备份中的 MariaDB 连接、数据库名、管理员用户名和 `password_hash` 合并回新的 `config/config.php`。

## 4. 创建数据库

使用 phpMyAdmin 或 MariaDB CLI 创建两个数据库：

```sql
CREATE DATABASE IF NOT EXISTS chrono_bangumi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS chrono_library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

数据库分工：

- `chrono_bangumi`：公共 Bangumi Archive 数据，只读。
- `chrono_library`：私人收藏与封面缓存，网站读写。

## 5. 导入数据库结构

SQL 文件只包含表结构、索引和必要约束，不包含用户数据、私人收藏或大量动画数据。脚本使用 `CREATE TABLE IF NOT EXISTS`，可以重复执行用于补齐缺失表。

```bash
mysql -u root -p chrono_bangumi < database/chrono_bangumi_schema.sql
mysql -u root -p chrono_library < database/chrono_library_schema.sql
```

如需在 phpMyAdmin 中单独补建索引，请分别进入对应数据库后导入单库索引文件，或用命令行指定数据库名：

```bash
mysql -u root -p chrono_bangumi < sql/create_chrono_bangumi_indexes.sql
mysql -u root -p chrono_library < sql/create_chrono_library_indexes.sql
```

导入表结构后，`chrono_bangumi` 仍然是空的。Bangumi Archive 数据需要离线导入：

```bash
python importer/import_archive_dump.py --dir data/archive/processed --dry-run
python importer/import_archive_dump.py --dir data/archive/processed
```

## 6. 创建数据库用户

不要使用 MariaDB `root` 或 NAS 管理员账号运行网站。建议创建单独用户：

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

如果 MariaDB 与 Web 服务在同一台机器，也可以把 `'%'` 改成 `'localhost'`。

## 7. 修改 `config/config.php`

编辑：

```text
/Web/ChronoShelter/config/config.php
```

填入 MariaDB 主机、端口、用户名、密码和数据库名。示例：

```php
'db' => [
    'host' => 'your-nas-ip',
    'port' => 3306,
    'user' => 'chronoshelter',
    'password' => 'change-this-password',
    'public_database' => 'chrono_bangumi',
    'library_database' => 'chrono_library',
    'charset' => 'utf8mb4',
],
```

## 8. 创建管理员密码

生成密码哈希：

```bash
php -r "echo password_hash('your-admin-password', PASSWORD_DEFAULT);"
```

将输出填入 `config/config.php`：

```php
'auth' => [
    'enabled' => true,
    'username' => 'admin',
    'password_hash' => 'paste-password-hash-here',
],
```

不要把明文密码写入配置文件。

首次部署请复制 `config/config-example.php` 为 `config/config.php`。`config/config.php` 不提交 Git；仓库只保留 `config/config-example.php` 作为唯一示例配置。PHP 网站和 Python importer 共用本地 `config/config.php`，不要新增 `db_config.py`、`database_config.py` 等第二套密码配置。

## 9. 部署检查

访问：

```text
http://your-nas-ip/ChronoShelter/install_check.php
```

检查项包括：

```text
PHP       OK
PDO MySQL OK
MariaDB   OK
Schema    OK
```

部署完成后建议删除或限制访问 `install_check.php`。

## 10. 测试访问

1. 打开站点首页。
2. 未登录时应跳转到 `login.php`。
3. 使用配置的管理员账号登录。
4. 首页应正常显示；如果 `chrono_bangumi` 尚未导入数据，页面可以为空，但不应出现 PHP Fatal Error。
5. 访问 `admin.php` 查看表数量。

## 11. 数据目录规范

大量 Archive jsonlines 不要放项目根目录，统一使用：

```text
data/
├── archive/
│   ├── incoming/      # archive.zip 等原始下载文件
│   ├── extracted/     # 解压临时目录
│   └── processed/     # 验证通过、供 importer 导入的数据
└── logs/              # 离线工具日志
```

## 12. 动画封面离线同步

网页请求不会下载 Bangumi 封面，也不会访问 `api.bgm.tv` 或 `lain.bgm.tv`。封面只由 PHP CLI 离线工具维护，并且固定只处理 Bangumi `type=2` 动画、批量接口 `GET /v0/subjects?type=2&limit=100&offset=...`、`images.large`。旧的 Python 单条目封面下载脚本已经禁用，避免误用 `/v0/subjects/{id}/image` 或远程默认图。

小规模验证（不会启动完整下载）：

```bash
php bin/bangumi_covers.php sync --max-pages=1 --max-items=10 --dry-run
```

首次全量下载或中断恢复（只在已明确决定执行全量同步的维护机器上运行）：

```bash
php bin/bangumi_covers.php sync --resume
```

后续检查和应用更新：

```bash
php bin/bangumi_covers.php check-updates --resume
php bin/bangumi_covers.php apply-updates --resume
php bin/bangumi_covers.php retry-failed
php bin/bangumi_covers.php deep-check --sample=100
php bin/bangumi_covers.php export-mapping --file=var/cover-sync/reports/cover-mapping.jsonl
php bin/bangumi_covers.php import-mapping --file=cover-mapping.jsonl
```

运行数据在非公开目录 `var/cover-sync/`，正式图片在 `covers/subjects/`，文件名保留 Bangumi `images.large` URL 的安全 basename，例如 `covers/subjects/000/001/1234_Ewjo.jpg`。正式服务器必须同时部署/同步 `covers/subjects/`、确保本地存在 `covers/logo.png`，并导入最新 `cover_cache.local_path` 映射；单独的 `var/cover-sync/covers.sqlite` 可只保留在维护机器。详见 `docs/bangumi_cover_sync.md`。

## 13. 索引兼容性说明

`subjects.name` 与 `subjects.name_cn` 是 `VARCHAR(512)` 且使用 `utf8mb4`。为了兼容 InnoDB 单索引键长度限制，联合索引 `idx_subjects_type_name_name_cn` 使用前缀索引：

```sql
CREATE INDEX IF NOT EXISTS `idx_subjects_type_name_name_cn`
ON `subjects` (`type`, `name`(191), `name_cn`(191));
```

不要改回完整 `name` / `name_cn` 联合索引，否则部分 MySQL/MariaDB 环境会因 key length 超过 3072 bytes 而导入失败。
