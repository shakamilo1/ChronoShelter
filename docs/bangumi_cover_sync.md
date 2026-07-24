# Bangumi 动画封面离线同步

ChronoShelter 的正式 Web 服务器不应依赖 Bangumi 网络可用性。网页请求只读取本地 `covers/` 静态文件；如果本地没有可用封面，立即回退到 `covers/logo.png`，不会访问 `api.bgm.tv` 或 `lain.bgm.tv`。

## 范围

封面同步系统只处理 Bangumi `type=2` 动画条目。不会下载或处理：

- `type=1` 书籍
- `type=3` 音乐
- `type=4` 游戏
- `type=6` 三次元

CLI 只调用批量接口：

```text
GET https://api.bgm.tv/v0/subjects?type=2&limit=50&offset={offset}
```

每页 `limit=50`，从 `offset=0` 开始，并只读取每个条目的 `images.large`。不会爬取 HTML 页面，也不会逐条调用 `/v0/subjects/{id}` 或 `/v0/subjects/{id}/image`。

## Python 环境

Windows 维护机建议使用 Python 3.12+，并安装测试/同步所需依赖（其中 Pillow 用于完整解码 JPEG、PNG、WebP）：

```powershell
python -m pip install -r requirements-dev.txt
```

同步器支持 `CHRONOSHELTER_COVERS_DIR` 指向 NAS SMB/UNC 封面目录，例如 `\\AS6604T-BA68\Web\chronoshelter-pr6-runtime\covers`，并支持 `CHRONOSHELTER_COVER_SYNC_STATE_DIR` 指向非公开状态目录。

## User-Agent 与可选 Token

默认 User-Agent：

```text
shakamilo1/ChronoShelter-cover-sync/1.0 (https://github.com/shakamilo1/ChronoShelter)
```

可选访问令牌通过环境变量提供：

```bash
export BANGUMI_ACCESS_TOKEN='你的 Bangumi access token'
```

有 Token 时，只有严格指向 `https://api.bgm.tv` 的 API JSON 请求会发送 `Authorization: Bearer <token>`；API 请求禁止自动跟随重定向，3xx 会失败。图片下载请求和图片重定向始终重新生成不含 Authorization 的请求头。没有 Token 时匿名运行。Token 不写入源码、配置示例、日志或 Git 仓库。匿名 API 结果可能不包含 NSFW 动画条目。

## 封面目录结构

正式封面只保存在 Web 可公开读取的 `covers/subjects/` 分片目录中；`covers/logo.png` 是部署时本地放置的 fallback，不随 Git 提交：

```text
covers/
├── logo.png
└── subjects/
    ├── 000/
    │   ├── 001/
    │   │   └── 1424_Ewjo.jpg
    │   ├── 062/
    │   │   └── 62229_abCd.jpg
    │   └── 491/
    │       └── 491569_xxxxx.jpg
    └── 001/
        └── 234/
            └── 1234567_rjOg.jpg
```

路径完全由数字 `subject_id` 和验证后的真实图片格式计算：

```text
level1 = intdiv(subject_id, 1000000)
level2 = intdiv(subject_id % 1000000, 1000)
```

`level1` 和 `level2` 至少补足为 3 位数字。例如：

- `1424` + `1424_Ewjo.jpg` -> `subjects/000/001/1424_Ewjo.jpg`
- `62229` -> `subjects/000/062/62229_abCd.jpg`
- `491569` -> `subjects/000/491/491569_xxxxx.jpg`
- `1234567` -> `subjects/001/234/1234567_rjOg.jpg`

目录分片只由 `subject_id` 计算；正式文件名来自 `images.large` URL path 的安全 basename，例如 `1234_Ewjo.jpg`。如果 basename 不安全或格式不符合当前条目，则退回 `{subject_id}_{URL SHA-256 前 12 位}.{ext}`。数据库 `local_path` 决定网页显示哪个文件，同一 subject_id 可能先后出现多个不同文件名；当前映射切换成功后，网站才显示新封面。不会使用远程 URL 的目录作为本地路径，数据库/清单只保存相对于 `covers/` 的路径。

## 同步清单

同步清单使用 SQLite，位于非公开目录：

```text
var/cover-sync/
├── covers.sqlite
├── tmp/
├── logs/
└── reports/
```

下载临时 `.part` 文件写入最终目标所在的 `covers/subjects/{level1}/{level2}/` 分片目录，验证完成前最终文件名不会出现；启动时会清理遗留 `.part`。测试或隔离运行可用 `CHRONOSHELTER_COVER_SYNC_STATE_DIR` 指向临时状态目录、`CHRONOSHELTER_COVERS_DIR` 指向临时封面根目录。SQLite 记录 `subject_id`、固定的 `subject_type=2`、`downloaded_url`、`observed_url`、`remote_filename`、`relative_path`、`mime_type`、`file_extension`、`file_size`、`sha256`、`etag`、`last_modified`、`artifact_status`、`deploy_status`、`last_check_result`、`last_error`、`checked_at`、`last_success_at`、`retry_count`。如果检测到旧 PHP 同步器留下的不兼容 `covers.sqlite`，Python 会立即退出并提示备份后使用新的 `CHRONOSHELTER_COVER_SYNC_STATE_DIR`，不会随机运行到缺列失败。同步进度记录 `run_type`、`next_offset`、`total` 和更新时间。

## 命令

小规模测试，最多扫描一页、最多处理 1 条（不会启动完整下载）：

```bash
python tools/download_covers.py sync --max-pages=1 --max-items=1 --api-delay=0 --download-delay=0 --verbose
```

首次全量同步或中断恢复（只在已明确授权的 Windows/VPN 维护机器上运行）：

```bash
python tools/download_covers.py sync --resume
```

验证已下载文件并导出 PHP 可导入的 JSONL 映射：

```bash
python tools/download_covers.py verify-files
python tools/download_covers.py export-mapping --file=var/cover-sync/reports/cover-mapping.jsonl
```

部署顺序必须是先复制 `covers/subjects/` 文件到 NAS/正式服务器，再导入映射：

```bash
php bin/bangumi_covers.php import-mapping --file=var/cover-sync/reports/cover-mapping.jsonl
```

NAS/PHP 只验证 JSONL、本地封面并事务导入 MariaDB `cover_cache`；联网同步、文件验证和映射导出都由 Python 同步器完成。常用开发限制参数：`--max-pages=1`、`--max-items=1`、`--verbose`。默认 `--download-delay=1`、`--api-delay=1`，Python 同步器保持串行保守下载。

## 图片验证与安全替换

CLI 只接受 JPEG、PNG、WebP。下载必须 HTTP 200、非空、Content-Type 与文件头匹配，且内容不能是 HTML/JSON 错误页或 Bangumi 默认无图占位；初始 URL 或手动重定向最终 URL 的 basename 为 `no_icon_subject.png` 时按无封面处理。离线 Python 验证会检查 Content-Type、文件头、格式结构、Pillow 完整解码、尺寸、大小和 SHA-256；验证通过后才原子落盘。更新封面时先保存新文件并更新清单；旧文件始终保留，直到未来有生产引用证明的显式清理流程确认可删。下载失败时保留旧封面。

`remote_missing` 默认不会删除旧封面，避免 Bangumi 短暂异常导致批量丢图。未来如需清理，应使用显式清理参数并先审查目标。

## 正式服务器部署

下载电脑完成同步后，正式服务器至少需要复制分片封面目录，并确认服务器本地已经放置 fallback：

```text
covers/subjects/
```

如果服务器还没有 `covers/logo.png`，可用仓库根目录的 `logo.png` 初始化：

```bash
cp logo.png covers/logo.png
```

如果希望保留同步状态或在正式服务器上执行 `verify-files`，也可以复制：

```text
var/cover-sync/covers.sqlite
```

`var/cover-sync/` 中的 SQLite、日志、锁文件、失败报告不需要复制到 Web 公开目录；`.part` 临时文件不应出现在完成后的封面分片目录中。建议用目录级增量同步工具复制新增和修改文件，不要每次重新传输整个封面库。

封面图片可能有独立版权，不要把整个封面库作为公开下载包发布。

## 映射导出和正式部署

下载机器和正式服务器可能不是同一台机器。默认离线同步只写 SQLite 清单并把新下载记录保留为 `pending_deploy`，不要求也不强制连接生产 MariaDB；完成离线同步后，先运行 `python tools/download_covers.py export-mapping --file=var/cover-sync/reports/cover-mapping.jsonl` 导出映射，再复制 `covers/subjects/` 中新增/更新的文件到正式服务器，并在正式服务器运行 `php bin/bangumi_covers.php import-mapping --file=cover-mapping.jsonl` 导入 `cover_cache`。不能只复制图片而不复制数据库映射；网页只根据 `cover_cache.local_path` 显示封面，网页本身永远不访问 Bangumi。确认网页使用新路径后，最后再清理不再被映射引用的旧文件。


### 封面清理安全规则

同步程序不会在新封面下载成功、SQLite 更新、MariaDB 写入或 import-mapping 时自动删除旧封面。SQLite 中旧的 `status` 列仅作兼容摘要，新的运行逻辑使用 `artifact_status` 表示最后成功文件是否可用、`deploy_status` 表示 `deployed`/`pending_deploy`/`mapping_failed`，以及 `last_check_result` 记录 `unchanged`、`updated`、`remote_missing`、`http_failed`、`local_invalid` 等最近检查结果。失败的 `pending_update`、`failed`、`mapping_failed`、`remote_missing` 不会污染网站当前 `cached` 映射；只要旧文件仍有效，export-mapping 会继续导出旧封面。本 PR 不提供实际封面删除命令；旧文件在确认不再被生产 `cover_cache` 或可信映射引用前必须保留。

## Windows Python + VPN + NAS SMB 部署

最终部署结构是：PHP 网站运行在 NAS 上，只读取 MariaDB/本地 `covers/`；Bangumi 联网同步在开启 VPN 的 Windows 上执行 `python tools/download_covers.py`。`CHRONOSHELTER_COVERS_DIR` 可以指向 NAS 的 UNC/SMB 共享路径（例如 `\\AS6604T-BA68\Web\chronoshelter-pr6-runtime\covers`），`CHRONOSHELTER_COVER_SYNC_STATE_DIR` 可以指向同一共享中的非公开状态目录。同步器只写 SQLite 状态、封面文件和 JSONL 映射，不连接生产 MariaDB；NAS 上只运行 `php bin/bangumi_covers.php import-mapping --file=...` 事务导入映射。

Windows PowerShell 小规模隔离测试（不设置 Token，只扫描一页、最多下载一张、使用全新 NAS 测试目录、不连接或修改生产 MariaDB）：

```powershell
Remove-Item Env:BANGUMI_ACCESS_TOKEN -ErrorAction SilentlyContinue
$env:CHRONOSHELTER_COVERS_DIR='\\AS6604T-BA68\Web\chronoshelter-pr6-runtime\covers'
$env:CHRONOSHELTER_COVER_SYNC_STATE_DIR='\\AS6604T-BA68\Web\chronoshelter-pr6-runtime\var\cover-sync'
python tools/download_covers.py sync --max-pages=1 --max-items=1 --api-delay=0 --download-delay=0 --proxy http://127.0.0.1:7890 --verbose
python tools/download_covers.py verify-files
python tools/download_covers.py export-mapping --file '\\AS6604T-BA68\Web\chronoshelter-pr6-runtime\var\cover-sync\reports\cover-mapping-test.jsonl'
```

NAS 侧导入命令：

```bash
php bin/bangumi_covers.php import-mapping --file=var/cover-sync/reports/cover-mapping-test.jsonl
```

无需修改 Windows `php.ini`；联网、证书和代理由 Windows Python 进程负责。标准 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 环境变量会被 Python 标准库代理处理；显式 `--proxy` 会覆盖本次同步使用的 HTTP/HTTPS 代理。

## 未来集成边界

本 PR 不实现主页按钮、Windows 服务或任务队列。后续集成应为：主页按钮 → NAS 创建待执行任务 → Windows 后台 Python worker 轮询任务 → 通过 Windows VPN 获取 Bangumi 数据和封面 → 写入 NAS 暂存区 → NAS 事务导入 MariaDB → 页面读取任务状态和进度。禁止未来通过 PHP `shell_exec()` 直接启动联网同步，也禁止让 NAS 直接调用 Windows Python；PHP 网站请求仍不得访问 Bangumi 或触发封面修复。
