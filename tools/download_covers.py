#!/usr/bin/env python3
"""Offline Bangumi anime cover synchronizer for ChronoShelter.

Runs on a maintenance machine (for example Windows with VPN) and writes covers,
SQLite state, and JSONL mapping files that the NAS/PHP deployment can import.
It never connects to production MariaDB.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from PIL import Image, UnidentifiedImageError
except Exception:  # pragma: no cover - exercised in dependency checks.
    Image = None  # type: ignore[assignment]
    UnidentifiedImageError = OSError  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://api.bgm.tv/v0/subjects"
SUBJECT_TYPE = 2
PAGE_LIMIT = 50
USER_AGENT = "shakamilo1/ChronoShelter-cover-sync/1.0 (https://github.com/shakamilo1/ChronoShelter)"
ALLOWED_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
FILENAME_RE_TEMPLATE = r"^{sid}_[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 128 * 1024
API_TOTAL_TIMEOUT = 60.0
API_MAX_BYTES = 2 * 1024 * 1024
IMAGE_TOTAL_TIMEOUT = 120.0
REQUIRED_MANIFEST_COLUMNS = {"subject_id", "subject_type", "downloaded_url", "observed_url", "remote_filename", "relative_path", "mime_type", "file_extension", "file_size", "sha256", "etag", "last_modified", "artifact_status", "deploy_status", "last_check_result", "last_error", "checked_at", "last_success_at", "retry_count"}
REQUIRED_SYNC_RUNS_COLUMNS = {"run_type", "next_offset", "total", "updated_at"}
REQUIRED_MANIFEST_NOT_NULL = {"subject_type", "retry_count"}
REQUIRED_SYNC_RUNS_NOT_NULL = {"next_offset", "updated_at"}
PYTHON_SCHEMA_VERSION = 1


class CoverSyncError(RuntimeError):
    pass


class RemoteMissingCover(CoverSyncError):
    pass


@dataclass
class DownloadMeta:
    tmp_path: Path
    final_url: str
    content_type: str
    extension: str
    file_size: int
    sha256: str
    etag: str | None = None
    last_modified: str | None = None


def covers_dir() -> Path:
    return Path(os.environ.get("CHRONOSHELTER_COVERS_DIR", PROJECT_ROOT / "covers"))


def state_dir() -> Path:
    return Path(os.environ.get("CHRONOSHELTER_COVER_SYNC_STATE_DIR", PROJECT_ROOT / "var" / "cover-sync"))


def tmp_dir() -> Path:
    return state_dir() / "tmp"


def reports_dir() -> Path:
    return state_dir() / "reports"


def sqlite_path() -> Path:
    return state_dir() / "covers.sqlite"


def ensure_dirs() -> None:
    for path in (state_dir(), tmp_dir(), reports_dir()):
        path.mkdir(parents=True, exist_ok=True)
    ensure_cover_root()
    cleanup_stale_parts()


def ensure_cover_root() -> None:
    root = covers_dir()
    if root.is_symlink():
        raise CoverSyncError("covers root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)


def cleanup_stale_parts() -> None:
    """Remove orphaned download temp files from previous interrupted runs only."""
    candidates: list[Path] = []
    if tmp_dir().exists():
        candidates.extend(tmp_dir().glob("*.part"))
    subjects = covers_dir() / "subjects"
    if subjects.exists():
        candidates.extend(subjects.rglob("*.part"))
    for path in candidates:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
        except OSError:
            print(f"WARNING: could not remove stale temp file: {path}", file=sys.stderr)


def table_shape(con: sqlite3.Connection, table: str) -> tuple[set[str], list[str], set[str]]:
    info = list(con.execute(f"PRAGMA table_info({table})"))
    columns = {row[1] for row in info}
    pk = [row[1] for row in sorted((row for row in info if row[5] > 0), key=lambda row: row[5])]
    not_null = {row[1] for row in info if row[3] > 0}
    return columns, pk, not_null


def connect_db() -> sqlite3.Connection:
    ensure_dirs()
    con = sqlite3.connect(sqlite_path())
    con.row_factory = sqlite3.Row
    if con.execute("PRAGMA user_version").fetchone()[0] not in (0, PYTHON_SCHEMA_VERSION):
        con.close()
        raise CoverSyncError("incompatible existing covers.sqlite schema version; back it up and set CHRONOSHELTER_COVER_SYNC_STATE_DIR to a fresh directory")
    existing = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cover_manifest'").fetchone()
    if existing:
        columns, pk, not_null = table_shape(con, "cover_manifest")
        if REQUIRED_MANIFEST_COLUMNS - columns or pk != ["subject_id"] or REQUIRED_MANIFEST_NOT_NULL - not_null:
            con.close()
            raise CoverSyncError("incompatible existing covers.sqlite cover_manifest schema; back it up and set CHRONOSHELTER_COVER_SYNC_STATE_DIR to a fresh directory")
    existing_runs = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_runs'").fetchone()
    if existing_runs:
        columns, pk, not_null = table_shape(con, "sync_runs")
        if REQUIRED_SYNC_RUNS_COLUMNS - columns or pk != ["run_type"] or REQUIRED_SYNC_RUNS_NOT_NULL - not_null:
            con.close()
            raise CoverSyncError("incompatible existing covers.sqlite sync_runs schema; back it up and set CHRONOSHELTER_COVER_SYNC_STATE_DIR to a fresh directory")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS cover_manifest (
            subject_id INTEGER PRIMARY KEY,
            subject_type INTEGER NOT NULL DEFAULT 2,
            downloaded_url TEXT,
            observed_url TEXT,
            remote_filename TEXT,
            relative_path TEXT,
            mime_type TEXT,
            file_extension TEXT,
            file_size INTEGER,
            sha256 TEXT,
            etag TEXT,
            last_modified TEXT,
            artifact_status TEXT,
            deploy_status TEXT,
            last_check_result TEXT,
            last_error TEXT,
            checked_at TEXT,
            last_success_at TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            run_type TEXT PRIMARY KEY,
            next_offset INTEGER NOT NULL DEFAULT 0,
            total INTEGER,
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute(f"PRAGMA user_version = {PYTHON_SCHEMA_VERSION}")
    return con


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def partition_prefix(subject_id: int) -> PurePosixPath:
    return PurePosixPath("subjects") / f"{subject_id // 1_000_000:03d}" / f"{(subject_id % 1_000_000) // 1_000:03d}"


def safe_remote_filename(subject_id: int, url: str, detected_ext: str) -> str:
    path = urllib.parse.urlparse(url).path
    basename = urllib.parse.unquote(PurePosixPath(path).name)
    if any(ch in basename for ch in ("/", "\\")) or ".." in basename or any(ord(ch) < 32 or ord(ch) == 127 for ch in basename):
        basename = ""
    match = re.match(FILENAME_RE_TEMPLATE.format(sid=re.escape(str(subject_id))), basename, re.I)
    if match:
        ext = match.group(1).lower().replace("jpeg", "jpg")
        if ext != detected_ext:
            raise CoverSyncError("remote filename extension does not match detected image type")
        return basename
    return f"{subject_id}_{sha256(url.encode('utf-8')).hexdigest()[:12]}.{detected_ext}"


def cover_relative_path(subject_id: int, filename: str) -> PurePosixPath:
    if not re.match(rf"^{subject_id}_[A-Za-z0-9_-]+(?:--[a-f0-9]{{12}}|--[a-f0-9]{{64}})?\.(jpg|jpeg|png|webp)$", filename, re.I):
        raise CoverSyncError("invalid cover filename")
    return partition_prefix(subject_id) / filename


def cover_absolute_path(relative: str | PurePosixPath) -> Path:
    rel = PurePosixPath(str(relative).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise CoverSyncError("unsafe cover path")
    return covers_dir() / Path(*rel.parts)


def ensure_under(root: Path, path: Path) -> None:
    root_real = root.resolve()
    target_real = path.resolve() if path.exists() else path.parent.resolve()
    if target_real != root_real and root_real not in target_real.parents:
        raise CoverSyncError("path escapes covers root")


def ensure_safe_existing_components(path: Path) -> None:
    root = covers_dir().resolve()
    current = covers_dir()
    if current.is_symlink():
        raise CoverSyncError("covers root must not be a symlink")
    rel_parts = path.relative_to(covers_dir()).parts
    for part in rel_parts:
        current = current / part
        if current.is_symlink():
            raise CoverSyncError("cover path component must not be a symlink")
        if current.exists():
            ensure_under(covers_dir(), current)


def shard_dir(subject_id: int) -> Path:
    directory = cover_absolute_path(partition_prefix(subject_id))
    ensure_safe_existing_components(directory)
    current = covers_dir()
    for part in directory.relative_to(covers_dir()).parts:
        current = current / part
        if current.is_symlink():
            raise CoverSyncError("cover shard component must not be a symlink")
        if not current.exists():
            current.mkdir()
        ensure_under(covers_dir(), current)
    return directory


def is_no_icon(url: str) -> bool:
    return PurePosixPath(urllib.parse.urlparse(url).path).name == "no_icon_subject.png"


def normalize_api_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.bgm.tv" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise CoverSyncError("refusing to send Bangumi API request outside https://api.bgm.tv:443")
    return parsed


def api_headers(url: str) -> dict[str, str]:
    normalize_api_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    token = os.environ.get("BANGUMI_ACCESS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def image_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "image/webp,image/png,image/jpeg,*/*;q=0.8"}
    for key, value in (extra or {}).items():
        if key.lower() == "authorization":
            continue
        headers[key] = value
    return headers


def proxy_handler(proxy: str | None) -> urllib.request.ProxyHandler:
    if proxy:
        return urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    return urllib.request.ProxyHandler()


def opener(proxy: str | None) -> urllib.request.OpenerDirector:
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            return None

    return urllib.request.build_opener(proxy_handler(proxy), urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirectHandler)


def remaining_time(deadline: float, what: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CoverSyncError(f"{what} exceeded total timeout")
    return remaining


def set_response_timeout(resp: Any, timeout: float) -> None:
    sock = getattr(getattr(getattr(resp, "fp", None), "raw", None), "_sock", None)
    if sock is not None and hasattr(sock, "settimeout"):
        sock.settimeout(timeout)


def read_limited_response(resp: Any, deadline: float, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        set_response_timeout(resp, remaining_time(deadline, "API request"))
        try:
            chunk = (resp.read1(CHUNK_SIZE) if hasattr(resp, "read1") else resp.read(CHUNK_SIZE))
        except TimeoutError as exc:
            raise CoverSyncError("API request exceeded total timeout") from exc
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise CoverSyncError("API response exceeds maximum allowed size")
        chunks.append(chunk)
    return b"".join(chunks)


def request_once(url: str, headers: dict[str, str], proxy: str | None, timeout: float, deadline: float | None = None, max_bytes: int = API_MAX_BYTES) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    deadline = deadline if deadline is not None else time.monotonic() + timeout
    socket_timeout = min(timeout, remaining_time(deadline, "API request"))
    try:
        with opener(proxy).open(req, timeout=socket_timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, read_limited_response(resp, deadline, max_bytes)
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, read_limited_response(exc, deadline, max_bytes)
    except urllib.error.URLError as exc:
        raise CoverSyncError(f"network error: {exc.reason}") from exc


def stream_once_to_tmp(url: str, headers: dict[str, str], proxy: str | None, timeout: float, tmp: Path, max_bytes: int = MAX_IMAGE_BYTES, total_timeout: float = IMAGE_TOTAL_TIMEOUT, deadline: float | None = None) -> tuple[int, dict[str, str], int]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    total = 0
    deadline = deadline if deadline is not None else time.monotonic() + total_timeout
    try:
        with opener(proxy).open(req, timeout=min(timeout, remaining_time(deadline, "image download"))) as resp, tmp.open("wb") as out:
            while True:
                set_response_timeout(resp, remaining_time(deadline, "image download"))
                try:
                    chunk = (resp.read1(CHUNK_SIZE) if hasattr(resp, "read1") else resp.read(CHUNK_SIZE))
                except TimeoutError as exc:
                    raise CoverSyncError("image download exceeded total timeout") from exc
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise CoverSyncError("image response exceeds maximum allowed size")
                out.write(chunk)
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, total
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, 0
    except urllib.error.URLError as exc:
        raise CoverSyncError(f"network error: {exc.reason}") from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def should_retry(status: int) -> bool:
    return status in {429, 500, 502, 503, 504}


def sleep_for_retry(headers: dict[str, str], attempt: int, deadline: float) -> None:
    retry_after = headers.get("retry-after")
    delay = min(30.0, float(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt) + random.random())
    remaining = remaining_time(deadline, "API request")
    if delay >= remaining:
        raise CoverSyncError("API retry delay exceeds remaining total timeout")
    time.sleep(delay)


def http_get(url: str, headers: dict[str, str], proxy: str | None, timeout: float, retries: int = 3, total_timeout: float = API_TOTAL_TIMEOUT) -> tuple[int, dict[str, str], bytes]:
    deadline = time.monotonic() + total_timeout
    for attempt in range(1, retries + 1):
        remaining_time(deadline, "API request")
        status, response_headers, body = request_once(url, headers, proxy, timeout, deadline, API_MAX_BYTES)
        if not should_retry(status) or attempt == retries:
            return status, response_headers, body
        sleep_for_retry(response_headers, attempt, deadline)
    raise AssertionError("unreachable")


def fetch_subject_page(offset: int, proxy: str | None, timeout: float = 30) -> dict[str, Any]:
    params = urllib.parse.urlencode({"type": SUBJECT_TYPE, "limit": PAGE_LIMIT, "offset": offset})
    url = f"{API_URL}?{params}"
    status, headers, body = http_get(url, api_headers(url), proxy, timeout)
    if 300 <= status < 400:
        raise CoverSyncError("Bangumi API redirect refused")
    if status != 200:
        raise CoverSyncError(f"Bangumi API failed: HTTP {status}")
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise CoverSyncError(f"Bangumi API JSON parse failed: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(data.get(k), int) and data[k] >= 0 for k in ("total", "limit", "offset")) or not isinstance(data.get("data"), list):
        raise CoverSyncError("Bangumi API Paged_Subject shape is invalid")
    if data["limit"] > PAGE_LIMIT or data["offset"] != offset:
        raise CoverSyncError("Bangumi API pagination fields do not match request")
    if offset < data["total"] and not data["data"]:
        raise CoverSyncError("Bangumi API returned empty data before total was reached")
    return data


def validate_image_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise CoverSyncError("invalid or unsafe image URL/redirect")
    return parsed


def follow_image_redirects_to_tmp(url: str, proxy: str | None, tmp: Path, timeout: float = 45, max_redirects: int = 5, total_timeout: float = IMAGE_TOTAL_TIMEOUT) -> tuple[int, dict[str, str], str]:
    current = url
    deadline = time.monotonic() + total_timeout
    for _ in range(max_redirects + 1):
        remaining_time(deadline, "image download")
        validate_image_url(current)
        if is_no_icon(current):
            raise RemoteMissingCover("Bangumi no-icon placeholder rejected")
        tmp.unlink(missing_ok=True)
        status, headers, _size = stream_once_to_tmp(current, image_headers(), proxy, timeout, tmp, deadline=deadline)
        if status in {301, 302, 303, 307, 308}:
            tmp.unlink(missing_ok=True)
            location = headers.get("location")
            if not location:
                raise CoverSyncError("image redirect missing Location")
            current = urllib.parse.urljoin(current, location)
            continue
        if is_no_icon(current):
            raise RemoteMissingCover("Bangumi no-icon placeholder rejected")
        return status, headers, current
    raise CoverSyncError("too many image redirects")


def follow_image_redirects(url: str, proxy: str | None, timeout: float = 45, max_redirects: int = 5) -> tuple[int, dict[str, str], bytes, str]:
    """Compatibility helper used by older tests; image downloads use streaming."""
    fd, name = tempfile.mkstemp(prefix="compat-", suffix=".part", dir=tmp_dir())
    os.close(fd)
    tmp = Path(name)
    try:
        status, headers, final_url = follow_image_redirects_to_tmp(url, proxy, tmp, timeout, max_redirects)
        return status, headers, tmp.read_bytes() if tmp.exists() else b"", final_url
    finally:
        tmp.unlink(missing_ok=True)


def image_type(data: bytes, content_type: str) -> tuple[str, str] | None:
    ctype = content_type.split(";", 1)[0].strip().lower()
    if data.startswith(b"\xff\xd8\xff") and ctype in {"image/jpeg", "image/jpg"}:
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n") and ctype == "image/png":
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and ctype == "image/webp":
        return "image/webp", "webp"
    return None


def validate_png(data: bytes) -> bool:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        chunk_type = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            return False
        expected = int.from_bytes(data[end:end + 4], "big")
        if zlib.crc32(chunk_type + data[start:end]) & 0xFFFFFFFF != expected:
            return False
        offset = end + 4
        if chunk_type == b"IEND":
            return offset == len(data)
    return False


def validate_image_file(path: Path, content_type: str) -> tuple[str, str, int, str]:
    ensure_safe_existing_components(path)
    if path.is_symlink():
        raise CoverSyncError("image path must not be a symlink")
    ensure_under(covers_dir(), path)
    if Image is None:
        raise CoverSyncError("Pillow is required for full image validation; install with: python -m pip install Pillow")
    data = path.read_bytes()
    if len(data) < 32 or len(data) > 20 * 1024 * 1024 or data.lstrip()[:1] in {b"<", b"{", b"["}:
        raise CoverSyncError("downloaded content is not a valid image")
    detected = image_type(data, content_type)
    if detected is None:
        raise CoverSyncError("unsupported or mismatched image type")
    mime, ext = detected
    if ext == "jpg" and not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
        raise CoverSyncError("JPEG structure is incomplete")
    if ext == "png" and not validate_png(data):
        raise CoverSyncError("PNG structure is incomplete or CRC is invalid")
    if ext == "webp" and (len(data) < 12 or int.from_bytes(data[4:8], "little") + 8 != len(data)):
        raise CoverSyncError("WebP RIFF length is invalid")
    try:
        with Image.open(path) as img:  # type: ignore[union-attr]
            expected_format = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[ext]
            if img.format != expected_format:
                raise CoverSyncError("Pillow image format does not match content type")
            width, height = img.size
            if width <= 0 or height <= 0:
                raise CoverSyncError("decoded image dimensions are invalid")
            img.verify()
        with Image.open(path) as img:  # type: ignore[union-attr]
            img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise CoverSyncError(f"Pillow failed to fully decode image: {exc}") from exc
    return mime, ext, len(data), sha256(data).hexdigest()


def download_image(subject_id: int, url: str, proxy: str | None) -> DownloadMeta:
    ensure_dirs()
    fd, name = tempfile.mkstemp(prefix=f".{subject_id}-", suffix=".part", dir=shard_dir(subject_id))
    os.close(fd)
    tmp = Path(name)
    try:
        status, headers, final_url = follow_image_redirects_to_tmp(url, proxy, tmp)
        if status != 200:
            raise CoverSyncError(f"image download failed: HTTP {status}")
        mime, ext, size, digest = validate_image_file(tmp, headers.get("content-type", ""))
        return DownloadMeta(tmp, final_url, mime, ext, size, digest, headers.get("etag"), headers.get("last-modified"))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def manifest_file_valid(row: sqlite3.Row) -> bool:
    try:
        if not row["relative_path"] or not row["sha256"] or not row["mime_type"] or row["file_size"] is None:
            return False
        path = cover_absolute_path(row["relative_path"])
        if path.is_symlink() or not path.is_file():
            return False
        ensure_under(covers_dir(), path)
        mime, ext, size, digest = validate_image_file(path, row["mime_type"])
        return mime == row["mime_type"] and ext == row["file_extension"] and size == int(row["file_size"]) and digest == row["sha256"]
    except Exception:
        return False



class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                if self.handle.read(1) == b"":
                    self.handle.write(b"0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(json.dumps({"pid": os.getpid(), "created_at": time.time(), "tool": "ChronoShelter Python cover sync"}).encode("utf-8"))
            self.handle.flush()
            os.fsync(self.handle.fileno())
            return self
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise CoverSyncError("another cover sync process holds the shard lock") from exc

    def __exit__(self, *_exc: object) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def acquire_lock(lock: Path) -> FileLock:
    return FileLock(lock)


def commit_tmp_no_clobber(tmp: Path, target: Path) -> None:
    shard_dir(int(target.name.split("_", 1)[0]))
    ensure_safe_existing_components(target.parent)
    ensure_under(covers_dir(), target.parent)
    lock = target.parent / ".chronoshelter-cover-sync.lock"
    with acquire_lock(lock):
        if target.is_symlink():
            raise CoverSyncError("target cover path is a symlink")
        if target.exists():
            raise FileExistsError(str(target))
        os.rename(tmp, target)
        ensure_under(covers_dir(), target)


def place_cover(subject_id: int, source_url: str, meta: DownloadMeta) -> tuple[str, str]:
    remote = safe_remote_filename(subject_id, source_url, meta.extension)
    rel = cover_relative_path(subject_id, remote)
    target = cover_absolute_path(rel)
    if target.is_symlink():
        raise CoverSyncError("target cover path is a symlink")
    if target.exists():
        ensure_under(covers_dir(), target)
        existing_sha = sha256(target.read_bytes()).hexdigest()
        if existing_sha == meta.sha256:
            meta.tmp_path.unlink(missing_ok=True)
            return remote, rel.as_posix()
        stem = Path(remote).stem
        ext = Path(remote).suffix.lstrip(".").lower().replace("jpeg", "jpg")
        for size in (12, 64):
            rel = cover_relative_path(subject_id, f"{stem}--{meta.sha256[:size]}.{ext}")
            target = cover_absolute_path(rel)
            if target.is_symlink():
                raise CoverSyncError("target cover path is a symlink")
            if not target.exists():
                break
            ensure_under(covers_dir(), target)
            if sha256(target.read_bytes()).hexdigest() == meta.sha256:
                meta.tmp_path.unlink(missing_ok=True)
                return remote, rel.as_posix()
    try:
        commit_tmp_no_clobber(meta.tmp_path, target)
    except Exception:
        meta.tmp_path.unlink(missing_ok=True)
        raise
    return remote, rel.as_posix()


def subject_url(item: dict[str, Any]) -> str | None:
    images = item.get("images")
    if not isinstance(images, dict):
        return None
    url = images.get("large")
    if not isinstance(url, str) or not url.strip() or is_no_icon(url):
        return None
    return url


def save_missing(con: sqlite3.Connection, subject_id: int, observed_url: str | None, result: str, error: str | None = None) -> None:
    old = con.execute("SELECT relative_path FROM cover_manifest WHERE subject_id=?", (subject_id,)).fetchone()
    artifact = "available" if old and old["relative_path"] else "missing"
    con.execute(
        """INSERT INTO cover_manifest (subject_id, subject_type, observed_url, artifact_status, deploy_status, last_check_result, last_error, checked_at)
        VALUES (?, 2, ?, ?, 'pending_deploy', ?, ?, ?)
        ON CONFLICT(subject_id) DO UPDATE SET observed_url=excluded.observed_url, artifact_status=?, last_check_result=excluded.last_check_result, last_error=excluded.last_error, checked_at=excluded.checked_at""",
        (subject_id, observed_url, artifact, result, error, now(), artifact),
    )
    con.commit()


def sync(args: argparse.Namespace) -> int:
    con = connect_db()
    run_type = "sync"
    offset = 0
    row = con.execute("SELECT next_offset FROM sync_runs WHERE run_type=?", (run_type,)).fetchone()
    if args.resume and row:
        offset = int(row["next_offset"])
    processed = 0
    pages = 0
    stats = {"downloaded": 0, "unchanged": 0, "remote_missing": 0, "failed": 0, "processed": 0, "next_offset": offset}
    while True:
        if args.max_pages is not None and pages >= args.max_pages:
            break
        page = fetch_subject_page(offset, args.proxy)
        total = int(page["total"])
        data = page["data"]
        if offset >= total:
            break
        for item in data:
            if args.max_items is not None and processed >= args.max_items:
                con.execute("INSERT INTO sync_runs (run_type,next_offset,total,updated_at) VALUES (?,?,?,?) ON CONFLICT(run_type) DO UPDATE SET next_offset=excluded.next_offset,total=excluded.total,updated_at=excluded.updated_at", (run_type, offset, total, now()))
                stats["next_offset"] = offset
                print(json.dumps(stats, ensure_ascii=False))
                return 1 if stats["failed"] else 0
            offset += 1
            if not isinstance(item, dict) or int(item.get("type", 0)) != SUBJECT_TYPE:
                continue
            subject_id = int(item.get("id", 0))
            if subject_id <= 0:
                raise CoverSyncError("invalid subject id")
            url = subject_url(item)
            if not url:
                save_missing(con, subject_id, None, "remote_missing")
                stats["remote_missing"] += 1
                if args.verbose:
                    print(f"remote_missing subject_id={subject_id}")
                processed += 1
                stats["processed"] = processed
                continue
            old = con.execute("SELECT * FROM cover_manifest WHERE subject_id=?", (subject_id,)).fetchone()
            if old and old["downloaded_url"] == url and manifest_file_valid(old):
                con.execute("UPDATE cover_manifest SET observed_url=?, artifact_status='available', last_check_result='unchanged', last_error=NULL, checked_at=? WHERE subject_id=?", (url, now(), subject_id))
                con.commit()
                stats["unchanged"] += 1
                if args.verbose:
                    print(f"unchanged subject_id={subject_id}")
                processed += 1
                stats["processed"] = processed
                continue
            try:
                meta = download_image(subject_id, url, args.proxy)
                remote, rel = place_cover(subject_id, url, meta)
                con.execute(
                    """INSERT INTO cover_manifest (subject_id, subject_type, downloaded_url, observed_url, remote_filename, relative_path, mime_type, file_extension, file_size, sha256, etag, last_modified, artifact_status, deploy_status, last_check_result, last_error, checked_at, last_success_at)
                    VALUES (?,2,?,?,?,?,?,?,?,?,?,?, 'available','pending_deploy','updated',NULL,?,?)
                    ON CONFLICT(subject_id) DO UPDATE SET downloaded_url=excluded.downloaded_url, observed_url=excluded.observed_url, remote_filename=excluded.remote_filename, relative_path=excluded.relative_path, mime_type=excluded.mime_type, file_extension=excluded.file_extension, file_size=excluded.file_size, sha256=excluded.sha256, etag=excluded.etag, last_modified=excluded.last_modified, artifact_status='available', deploy_status='pending_deploy', last_check_result='updated', last_error=NULL, checked_at=excluded.checked_at, last_success_at=excluded.last_success_at""",
                    (subject_id, url, url, remote, rel, meta.content_type, meta.extension, meta.file_size, meta.sha256, meta.etag, meta.last_modified, now(), now()),
                )
                con.commit()
                stats["downloaded"] += 1
                if args.verbose:
                    print(f"downloaded subject_id={subject_id} path={rel}")
            except RemoteMissingCover:
                save_missing(con, subject_id, url, "remote_missing")
                stats["remote_missing"] += 1
                if args.verbose:
                    print(f"remote_missing subject_id={subject_id}")
            except Exception as exc:
                save_missing(con, subject_id, url, "http_failed", str(exc))
                stats["failed"] += 1
                if args.verbose:
                    print(f"failed subject_id={subject_id} reason={exc}")
            processed += 1
            stats["processed"] = processed
            if args.download_delay:
                time.sleep(args.download_delay)
        pages += 1
        con.execute("INSERT INTO sync_runs (run_type,next_offset,total,updated_at) VALUES (?,?,?,?) ON CONFLICT(run_type) DO UPDATE SET next_offset=excluded.next_offset,total=excluded.total,updated_at=excluded.updated_at", (run_type, offset, total, now()))
        con.commit()
        stats["next_offset"] = offset
        if offset >= total:
            break
        if args.api_delay:
            time.sleep(args.api_delay)
    stats["processed"] = processed
    stats["next_offset"] = offset
    print(json.dumps(stats, ensure_ascii=False))
    return 1 if stats["failed"] else 0


def verify_files(args: argparse.Namespace) -> int:
    con = connect_db()
    failed = 0
    for row in con.execute("SELECT * FROM cover_manifest WHERE relative_path IS NOT NULL"):
        path = cover_absolute_path(row["relative_path"])
        try:
            mime, ext, size, digest = validate_image_file(path, row["mime_type"] or "")
            if ext != row["file_extension"] or size != row["file_size"] or digest != row["sha256"]:
                raise CoverSyncError("metadata mismatch")
        except Exception as exc:
            failed += 1
            con.execute("UPDATE cover_manifest SET artifact_status='invalid', last_check_result='local_invalid', last_error=?, checked_at=? WHERE subject_id=?", (str(exc), now(), row["subject_id"]))
    con.commit()
    print(json.dumps({"failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


def export_mapping(args: argparse.Namespace) -> int:
    con = connect_db()
    out = Path(args.file or reports_dir() / f"cover-mapping-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in con.execute("SELECT * FROM cover_manifest ORDER BY subject_id"):
            if row["relative_path"] and row["sha256"] and row["artifact_status"] != "invalid" and manifest_file_valid(row):
                item = {"subject_id": row["subject_id"], "status": "cached", "remote_filename": row["remote_filename"], "source_url": row["downloaded_url"], "local_path": row["relative_path"], "content_type": row["mime_type"], "file_size": row["file_size"], "sha256": row["sha256"], "updated_at": row["last_success_at"] or row["checked_at"]}
            elif row["artifact_status"] == "missing" and row["last_check_result"] == "remote_missing":
                item = {"subject_id": row["subject_id"], "status": "no_cover", "remote_filename": None, "source_url": None, "local_path": None, "content_type": None, "file_size": None, "sha256": None, "updated_at": row["checked_at"]}
            else:
                continue
            fh.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    print(json.dumps({"file": str(out), "records": count}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Bangumi anime cover synchronizer (type=2 only).")
    sub = parser.add_subparsers(dest="command", required=True)
    sync_p = sub.add_parser("sync")
    sync_p.add_argument("--resume", action="store_true")
    sync_p.add_argument("--max-pages", type=int)
    sync_p.add_argument("--max-items", type=int)
    sync_p.add_argument("--api-delay", type=float, default=1.0)
    sync_p.add_argument("--download-delay", type=float, default=1.0)
    sync_p.add_argument("--verbose", action="store_true")
    sync_p.add_argument("--proxy")
    verify_p = sub.add_parser("verify-files")
    verify_p.add_argument("--verbose", action="store_true")
    export_p = sub.add_parser("export-mapping")
    export_p.add_argument("--file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sync":
            return sync(args)
        if args.command == "verify-files":
            return verify_files(args)
        if args.command == "export-mapping":
            return export_mapping(args)
        raise CoverSyncError("unknown command")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
