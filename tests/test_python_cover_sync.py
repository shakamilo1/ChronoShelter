from __future__ import annotations

import importlib.util
import json
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("download_covers", ROOT / "tools" / "download_covers.py")
dl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = dl
SPEC.loader.exec_module(dl)


def png_bytes() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return len(payload).to_bytes(4, "big") + kind + payload + zlib.crc32(kind + payload).to_bytes(4, "big")
    raw = b"\x00\x00\x00\x00"  # filter + RGB pixel
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00") + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def configure_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    covers = tmp_path / "nas share" / "covers"
    state = tmp_path / "nas share" / "state"
    monkeypatch.setenv("CHRONOSHELTER_COVERS_DIR", str(covers))
    monkeypatch.setenv("CHRONOSHELTER_COVER_SYNC_STATE_DIR", str(state))
    return covers, state


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


def test_python_proxy_explicit_and_environment(monkeypatch):
    handler = dl.proxy_handler("http://127.0.0.1:8888")
    assert handler.proxies["http"] == "http://127.0.0.1:8888"
    assert handler.proxies["https"] == "http://127.0.0.1:8888"
    monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:8080")
    env_handler = dl.proxy_handler(None)
    assert "https" in env_handler.proxies


def test_python_sync_rejects_no_icon_and_exports_mapping(monkeypatch, tmp_path):
    covers, state = configure_paths(monkeypatch, tmp_path)
    body = png_bytes()
    calls: list[str] = []

    def fake_request(url, headers, proxy, timeout):
        calls.append(url)
        if url.startswith(dl.API_URL):
            page = {
                "total": 2,
                "limit": 50,
                "offset": 0,
                "data": [
                    {"id": 491569, "type": 2, "images": {"large": "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png"}},
                    {"id": 491570, "type": 2, "images": {"large": "https://lain.bgm.tv/img/no_icon_subject.png"}},
                ],
            }
            return 200, {"content-type": "application/json"}, json.dumps(page).encode()
        return 200, {"content-type": "image/png"}, body

    monkeypatch.setattr(dl, "request_once", fake_request)
    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)
    rc = dl.sync(dl.build_parser().parse_args(["sync", "--max-pages=1", "--max-items=2", "--api-delay=0", "--download-delay=0"]))
    assert rc == 0
    cover = covers / "subjects" / "000" / "491" / "491569_ok.png"
    assert cover.is_file()
    assert not list((state / "tmp").glob("*.part"))
    out = tmp_path / "mapping.jsonl"
    assert dl.export_mapping(dl.build_parser().parse_args(["export-mapping", f"--file={out}"])) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[0]["status"] == "cached"
    assert rows[0]["local_path"] == "subjects/000/491/491569_ok.png"
    assert rows[1]["status"] == "no_cover"


def test_python_redirect_rejects_https_downgrade_and_token_never_sent(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    seen_headers = []

    def fake_once(url, headers, proxy, timeout):
        seen_headers.append(headers)
        if len(seen_headers) == 1:
            return 302, {"location": "http://evil.example/491569_ok.png"}, b""
        return 200, {"content-type": "image/png"}, png_bytes()

    monkeypatch.setattr(dl, "request_once", fake_once)
    try:
        dl.download_image(491569, "https://lain.bgm.tv/pic/cover/l/a/b/491569_ok.png", None)
    except dl.CoverSyncError:
        pass
    else:
        raise AssertionError("downgrade redirect was accepted")
    assert all("Authorization" not in headers for headers in seen_headers)
    assert not list((tmp_path / "nas share" / "state" / "tmp").glob("*.part"))


def test_python_unc_style_paths_are_accepted(monkeypatch, tmp_path):
    unc_like = "\\\\AS6604T-BA68\\Web\\chronoshelter-pr6-runtime\\covers"
    monkeypatch.setenv("CHRONOSHELTER_COVERS_DIR", unc_like)
    assert "AS6604T-BA68" in str(dl.covers_dir())
    assert dl.partition_prefix(1234567).as_posix() == "subjects/001/234"
