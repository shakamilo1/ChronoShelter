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

首次部署复制示例配置，本地真实配置不要提交 Git：

```bash
cd /Web/ChronoShelter
cp config-example.php config.php
```

唯一测试目录是项目根目录下的 `tests/`，`pytest.ini` 也位于项目根目录。请从 `ChronoShelter/` 运行 `pytest`，避免重复 clone 到子目录导致 `import file mismatch`。

## 3. 创建数据库

使用 phpMyAdmin 或 MariaDB CLI 创建两个数据库：

```sql
CREATE DATABASE IF NOT EXISTS chrono_bangumi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS chrono_library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

数据库分工：

- `chrono_bangumi`：公共 Bangumi Archive 数据，只读。
- `chrono_library`：私人收藏与封面缓存，网站读写。

## 4. 导入数据库结构

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

## 5. 创建数据库用户

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

## 6. 修改 `config.php`

编辑：

```text
/Web/ChronoShelter/config.php
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

## 7. 创建管理员密码

生成密码哈希：

```bash
php -r "echo password_hash('your-admin-password', PASSWORD_DEFAULT);"
```

将输出填入 `config.php`：

```php
'auth' => [
    'enabled' => true,
    'username' => 'admin',
    'password_hash' => 'paste-password-hash-here',
],
```

不要把明文密码写入配置文件。

`config.php` 已被 `.gitignore` 忽略；仓库只提交 `config-example.php`。以后执行 `git pull` 不会覆盖你的本地真实配置。新增示例配置时使用 `文件名-example.扩展名` 命名，例如 `.env-example`、`local_config-example.py`。

## 8. 部署检查

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

## 9. 测试访问

1. 打开站点首页。
2. 未登录时应跳转到 `login.php`。
3. 使用配置的管理员账号登录。
4. 首页应正常显示；如果 `chrono_bangumi` 尚未导入数据，页面可以为空，但不应出现 PHP Fatal Error。
5. 访问 `admin.php` 查看表数量。

## 10. 数据目录规范

大量 Archive jsonlines 不要放项目根目录，统一使用：

```text
data/
├── archive/
│   ├── incoming/      # archive.zip 等原始下载文件
│   ├── extracted/     # 解压临时目录
│   └── processed/     # 验证通过、供 importer 导入的数据
└── logs/              # 离线工具日志
```

## 11. 封面批量下载

安装离线工具依赖：

```bash
python -m pip install PyMySQL Pillow
```

运行：

```bash
python tools/download_covers.py --missing --limit 500 --delay 3
```

失败日志位于：

```text
logs/cover_download.log
```

## 12. 索引兼容性说明

`subjects.name` 与 `subjects.name_cn` 是 `VARCHAR(512)` 且使用 `utf8mb4`。为了兼容 InnoDB 单索引键长度限制，联合索引 `idx_subjects_type_name_name_cn` 使用前缀索引：

```sql
CREATE INDEX IF NOT EXISTS `idx_subjects_type_name_name_cn`
ON `subjects` (`type`, `name`(191), `name_cn`(191));
```

不要改回完整 `name` / `name_cn` 联合索引，否则部分 MySQL/MariaDB 环境会因 key length 超过 3072 bytes 而导入失败。
