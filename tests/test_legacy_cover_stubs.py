import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_script(script):
    return subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, text=True, capture_output=True, check=False)


def test_download_covers_cli_is_restored_with_help():
    result = subprocess.run([sys.executable, str(ROOT / "tools/download_covers.py"), "--help"], cwd=ROOT, text=True, capture_output=True, check=False)

    assert result.returncode == 0
    assert "sync" in result.stdout
    assert "export-mapping" in result.stdout


def test_cache_covers_stub_points_to_php_sync():
    result = run_script("tools/cache_covers.py")

    assert result.returncode == 2
    assert "python tools/download_covers.py sync" in result.stderr
