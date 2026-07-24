from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("download_covers", ROOT / "tools" / "download_covers.py")
dl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = dl
SPEC.loader.exec_module(dl)


class FakeImageObj:
    format = "PNG"
    size = (1, 1)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def verify(self): return None
    def load(self): return None


class FakeImageModule:
    @staticmethod
    def open(_path):
        return FakeImageObj()


def enable_fake_pillow(monkeypatch):
    monkeypatch.setattr(dl, "Image", FakeImageModule)


def png_bytes() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return len(payload).to_bytes(4, "big") + kind + payload + zlib.crc32(kind + payload).to_bytes(4, "big")
    raw = b"\x00\x00\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00") + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def configure_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    covers = tmp_path / "nas share" / "covers"
    state = tmp_path / "nas share" / "state"
    monkeypatch.setenv("CHRONOSHELTER_COVERS_DIR", str(covers))
    monkeypatch.setenv("CHRONOSHELTER_COVER_SYNC_STATE_DIR", str(state))
    return covers, state


def assert_no_parts(root: Path):
    assert not list(root.rglob("*.part"))


def test_python_headers_scope_token_and_images_strip_authorization(monkeypatch):
    monkeypatch.setenv("BANGUMI_ACCESS_TOKEN", "fake-token")
    api = dl.api_headers("https://api.bgm.tv/v0/subjects")
    assert api["Authorization"] == "Bearer fake-token"
    for bad in ["https://api.bgm.tv.evil/v0/subjects", "https://api.bgm.tv:444/v0/subjects", "http://api.bgm.tv/v0/subjects", "https://api.bgm.tv@evil.example/v0/subjects"]:
        try:
            dl.api_headers(bad)
        except dl.CoverSyncError:
            pass
        else:
            raise AssertionError(f"accepted bad api URL: {bad}")
    image = dl.image_headers({"Authorization": "Bearer fake-token", "If-None-Match": "abc"})
    assert "Authorization" not in image
    assert image["If-None-Match"] == "abc"


def test_real_transport_api_does_not_auto_redirect(monkeypatch):
    seen: list[str] = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if self.path == "/api":
                self.send_response(302)
                self.send_header("Location", "/evil")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
        def log_message(self, *_args):
            return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _headers, _body = dl.request_once(f"http://127.0.0.1:{server.server_port}/api", {"Authorization": "Bearer fake"}, None, 5)
        assert status == 302
        assert seen == ["/api"]
    finally:
        server.shutdown()
        thread.join(5)


def test_python_proxy_explicit_and_environment(monkeypatch):
    handler = dl.proxy_handler("http://127.0.0.1:8888")
    assert handler.proxies["http"] == "http://127.0.0.1:8888"
    assert handler.proxies["https"] == "http://127.0.0.1:8888"
    monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:8080")
    env_handler = dl.proxy_handler(None)
    assert "https" in env_handler.proxies


def test_python_sync_rejects_no_icon_and_exports_mapping(monkeypatch, tmp_path):
    enable_fake_pillow(monkeypatch)
    covers, state = configure_paths(monkeypatch, tmp_path)
    body = png_bytes()

    def fake_request(url, headers, proxy, timeout):
        if url.startswith(dl.API_URL):
            page = {"total": 2, "limit": 50, "offset": 0, "data": [
                {"id": 491569, "type": 2, "images": {"large": "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png"}},
                {"id": 491570, "type": 2, "images": {"large": "https://lain.bgm.tv/img/no_icon_subject.png"}},
            ]}
            return 200, {"content-type": "application/json"}, json.dumps(page).encode()
        raise AssertionError("unexpected request")

    def fake_stream(url, headers, proxy, timeout, tmp, max_bytes=dl.MAX_IMAGE_BYTES):
        assert "Authorization" not in headers
        tmp.write_bytes(body)
        return 200, {"content-type": "image/png"}, len(body)

    monkeypatch.setattr(dl, "request_once", fake_request)
    monkeypatch.setattr(dl, "stream_once_to_tmp", fake_stream)
    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)
    rc = dl.sync(dl.build_parser().parse_args(["sync", "--max-pages=1", "--max-items=2", "--api-delay=0", "--download-delay=0", "--verbose"]))
    assert rc == 0
    cover = covers / "subjects" / "000" / "491" / "491569_ok.png"
    assert cover.is_file()
    assert_no_parts(tmp_path)
    out = tmp_path / "mapping.jsonl"
    assert dl.export_mapping(dl.build_parser().parse_args(["export-mapping", f"--file={out}"])) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["status"] == "cached"
    assert rows[0]["local_path"] == "subjects/000/491/491569_ok.png"
    assert rows[1]["status"] == "no_cover"


def test_python_redirect_rejects_https_downgrade_and_token_never_sent(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    seen_headers = []
    def fake_stream(url, headers, proxy, timeout, tmp, max_bytes=dl.MAX_IMAGE_BYTES):
        seen_headers.append(headers)
        return 302, {"location": "http://evil.example/491569_ok.png"}, 0
    monkeypatch.setattr(dl, "stream_once_to_tmp", fake_stream)
    try:
        dl.download_image(491569, "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png", None)
    except dl.CoverSyncError:
        pass
    else:
        raise AssertionError("downgrade redirect was accepted")
    assert all("Authorization" not in headers for headers in seen_headers)
    assert_no_parts(tmp_path)


def test_python_download_validation_failure_cleans_part(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(dl, "Image", None)
    def fake_stream(url, headers, proxy, timeout, tmp, max_bytes=dl.MAX_IMAGE_BYTES):
        tmp.write_bytes(png_bytes())
        return 200, {"content-type": "image/png"}, tmp.stat().st_size
    monkeypatch.setattr(dl, "stream_once_to_tmp", fake_stream)
    try:
        dl.download_image(491569, "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png", None)
    except dl.CoverSyncError as exc:
        assert "Pillow is required" in str(exc)
    else:
        raise AssertionError("missing Pillow was accepted")
    assert_no_parts(tmp_path)


def test_python_invalid_file_redownloads_and_export_skips_invalid(monkeypatch, tmp_path):
    enable_fake_pillow(monkeypatch)
    covers, _state = configure_paths(monkeypatch, tmp_path)
    body = png_bytes()
    bad = covers / "subjects" / "000" / "491" / "491569_ok.png"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"broken")
    con = dl.connect_db()
    con.execute("INSERT INTO cover_manifest(subject_id, subject_type, downloaded_url, observed_url, remote_filename, relative_path, mime_type, file_extension, file_size, sha256, artifact_status, deploy_status, last_check_result) VALUES (491569,2,?,?,?,?,?,?,?,?,?,?,?)", ("https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png", "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png", "491569_ok.png", "subjects/000/491/491569_ok.png", "image/png", "png", 999, "0"*64, "invalid", "pending_deploy", "local_invalid"))
    con.commit(); con.close()
    out = tmp_path / "mapping.jsonl"
    assert dl.export_mapping(dl.build_parser().parse_args(["export-mapping", f"--file={out}"])) == 0
    assert out.read_text() == ""

    def fake_request(url, headers, proxy, timeout):
        page = {"total": 1, "limit": 50, "offset": 0, "data": [{"id": 491569, "type": 2, "images": {"large": "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png"}}]}
        return 200, {"content-type": "application/json"}, json.dumps(page).encode()
    def fake_stream(url, headers, proxy, timeout, tmp, max_bytes=dl.MAX_IMAGE_BYTES):
        tmp.write_bytes(body)
        return 200, {"content-type": "image/png"}, len(body)
    monkeypatch.setattr(dl, "request_once", fake_request)
    monkeypatch.setattr(dl, "stream_once_to_tmp", fake_stream)
    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)
    assert dl.sync(dl.build_parser().parse_args(["sync", "--max-pages=1", "--api-delay=0", "--download-delay=0"])) == 0
    assert bad.read_bytes() == b"broken"
    assert list((covers / "subjects" / "000" / "491").glob("491569_ok--*.png"))
    rows = list(dl.connect_db().execute("SELECT * FROM cover_manifest WHERE subject_id=491569"))
    assert rows[0]["artifact_status"] == "available"
    assert rows[0]["sha256"] == dl.sha256(body).hexdigest()


def test_python_unc_style_paths_are_accepted(monkeypatch):
    unc_like = "\\\\AS6604T-BA68\\Web\\chronoshelter-pr6-runtime\\covers"
    monkeypatch.setenv("CHRONOSHELTER_COVERS_DIR", unc_like)
    assert "AS6604T-BA68" in str(dl.covers_dir())
    assert dl.partition_prefix(1234567).as_posix() == "subjects/001/234"


def test_python_old_php_sqlite_schema_is_rejected(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    db = tmp_path / "nas share" / "state" / "covers.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cover_manifest (subject_id INTEGER PRIMARY KEY, status TEXT)")
    con.commit(); con.close()
    try:
        dl.connect_db()
    except dl.CoverSyncError as exc:
        assert "incompatible existing covers.sqlite schema" in str(exc)
    else:
        raise AssertionError("old incompatible PHP sqlite schema was accepted")


def test_python_atomic_commit_rename_failure_cleans_part(monkeypatch, tmp_path):
    enable_fake_pillow(monkeypatch)
    covers, _state = configure_paths(monkeypatch, tmp_path)
    body = png_bytes()
    dl.ensure_dirs()
    tmp = dl.shard_dir(491569) / ".491569-test.part"
    tmp.write_bytes(body)
    meta = dl.DownloadMeta(tmp, "https://lain.bgm.tv/pic/cover/l/a/b/491569_atomic.png", "image/png", "png", len(body), dl.sha256(body).hexdigest())
    def fail_rename(src, dst):
        raise OSError("simulated SMB rename failure")
    monkeypatch.setattr(dl.os, "rename", fail_rename)
    try:
        dl.place_cover(491569, meta.final_url, meta)
    except OSError as exc:
        assert "simulated SMB rename failure" in str(exc)
    else:
        raise AssertionError("rename failure was accepted")
    assert_no_parts(tmp_path)
    assert not (covers / "subjects" / "000" / "491" / "491569_atomic.png").exists()


def test_python_target_symlink_and_parent_symlink_are_rejected(monkeypatch, tmp_path):
    covers, _state = configure_paths(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    subjects = covers / "subjects"
    covers.mkdir(parents=True)
    subjects.symlink_to(outside, target_is_directory=True)
    try:
        dl.shard_dir(491569)
    except dl.CoverSyncError:
        pass
    else:
        raise AssertionError("subjects symlink was accepted")
    subjects.unlink()
    shard = covers / "subjects" / "000" / "491"
    shard.mkdir(parents=True)
    target = shard / "491569_link.png"
    target.symlink_to(outside / "escape.png")
    body = png_bytes()
    tmp = shard / ".491569-link.part"
    tmp.write_bytes(body)
    meta = dl.DownloadMeta(tmp, "https://lain.bgm.tv/pic/cover/l/a/b/491569_link.png", "image/png", "png", len(body), dl.sha256(body).hexdigest())
    try:
        dl.place_cover(491569, meta.final_url, meta)
    except dl.CoverSyncError:
        pass
    else:
        raise AssertionError("target symlink was accepted")
    tmp.unlink(missing_ok=True)


def test_python_stream_total_timeout_cleans_part(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    times = iter([0.0, 10.0])
    monkeypatch.setattr(dl.time, "monotonic", lambda: next(times, 10.0))
    class FakeResp:
        status = 200
        headers = {"content-type": "image/png"}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, _n): return b"x" * 10
    class FakeOpener:
        def open(self, _req, timeout): return FakeResp()
    monkeypatch.setattr(dl, "opener", lambda proxy: FakeOpener())
    tmp = tmp_path / "slow.part"
    try:
        dl.stream_once_to_tmp("https://images.example/slow.png", {}, None, 1, tmp, total_timeout=1)
    except dl.CoverSyncError as exc:
        assert "total timeout" in str(exc)
    else:
        raise AssertionError("slow stream was accepted")
    assert not tmp.exists()
