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

临时下载文件写入 `var/cover-sync/tmp/`，不会写入公开的 `covers/`。SQLite 记录 `subject_id`、固定的 `subject_type=2`、`downloaded_url`、`observed_url`、`relative_path`、`mime_type`、`file_extension`、`file_size`、`sha256`、`etag`、`last_modified`、状态、时间戳、重试次数和错误信息；同时预留并幂等迁移 `artifact_status`、`deploy_status`、`last_check_result`、`last_error`、`checked_at`、`last_success_at`，用于区分最后成功文件、部署状态和本次远端检查结果。同步进度记录 `run_id`、`run_type`、`next_offset`、`total`、开始/更新时间、完成时间和运行状态。

## 命令

小规模测试，最多扫描一页、最多处理 10 条：

```bash
php bin/bangumi_covers.php sync --max-pages=1 --max-items=10 --dry-run
```

首次全量同步或补齐缺失封面：

```bash
php bin/bangumi_covers.php sync --resume
```

中断后继续：

```bash
php bin/bangumi_covers.php sync --resume
```

手动检查新动画和封面 URL 变化，只生成清单和报告，不立即替换图片：

```bash
php bin/bangumi_covers.php check-updates --resume
```

报告输出到：

```text
var/cover-sync/reports/cover-changes-YYYY-MM-DD.json
var/cover-sync/reports/cover-changes-YYYY-MM-DD.txt
```

应用已发现的新封面或变化：

```bash
php bin/bangumi_covers.php apply-updates --resume
```

重试失败项目：

```bash
php bin/bangumi_covers.php retry-failed
```

检查本地文件是否存在、是否损坏：

```bash
php bin/bangumi_covers.php verify-files
```

随机深度抽查远程内容是否在相同 URL 下变化：

```bash
php bin/bangumi_covers.php deep-check --sample=100
```

核实指定动画：

```bash
php bin/bangumi_covers.php deep-check --subject-id=491569
```

只有显式确认时才允许检查全部：

```bash
php bin/bangumi_covers.php deep-check --all --confirm-all
```

常用开发限制参数：`--max-pages=1`、`--max-items=10`、`--dry-run`。默认 `--download-delay=1`、`--api-delay=1`、`--concurrency=1`，实现保持串行保守下载。

## 图片验证与安全替换

CLI 只接受 JPEG、PNG、WebP。下载必须 HTTP 200、非空、Content-Type 与文件头匹配，且内容不能是 HTML/JSON 错误页或 Bangumi 默认无图占位；初始 URL 或手动重定向最终 URL 的 basename 为 `no_icon_subject.png` 时按无封面处理。离线验证会检查 finfo、getimagesize、格式结构和 GD/Imagick 完整解码，验证通过后才计算 SHA-256 并落盘。更新封面时先保存新文件并更新清单；旧文件始终保留，直到未来有生产引用证明的显式清理流程确认可删。下载失败时保留旧封面。

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

`var/cover-sync/tmp/`、日志、锁文件、失败报告不需要复制到 Web 公开目录。建议用目录级增量同步工具复制新增和修改文件，不要每次重新传输整个封面库。

封面图片可能有独立版权，不要把整个封面库作为公开下载包发布。

## 映射导出和正式部署

下载机器和正式服务器可能不是同一台机器。默认离线同步只写 SQLite 清单并把新下载记录保留为 `pending_deploy`，不要求也不强制连接生产 MariaDB；只有明确传入 `--write-mysql` 时才会尝试直接写 `cover_cache`，失败才会标记 `mapping_failed`。完成离线同步后，先运行 `php bin/bangumi_covers.php export-mapping --file=var/cover-sync/reports/cover-mapping.jsonl` 导出映射，再复制 `covers/subjects/` 中新增/更新的文件到正式服务器，并在正式服务器运行 `php bin/bangumi_covers.php import-mapping --file=cover-mapping.jsonl` 导入 `cover_cache`。不能只复制图片而不复制数据库映射；网页只根据 `cover_cache.local_path` 显示封面，网页本身永远不访问 Bangumi。确认网页使用新路径后，最后再清理不再被映射引用的旧文件。


### 封面清理安全规则

同步程序不会在新封面下载成功、SQLite 更新、MariaDB 写入或 import-mapping 时自动删除旧封面。失败的 `pending_update`、`failed`、`mapping_failed`、`remote_missing` 不会污染网站当前 `cached` 映射；只要旧文件仍有效，export-mapping 会继续导出旧封面。需要清理时先运行 `php bin/bangumi_covers.php cleanup-covers` 查看 dry-run 候选；当前 `--apply` 会拒绝执行并返回 2，直到实现可靠的生产 `cover_cache` 引用或可信活动映射快照校验后才允许真实删除。
