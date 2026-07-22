import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_script(script):
    return subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, text=True, capture_output=True, check=False)


def test_download_covers_stub_points_to_php_sync():
    result = run_script("tools/download_covers.py")

    assert result.returncode == 2
    assert "php bin/bangumi_covers.php sync --resume" in result.stderr


def test_cache_covers_stub_points_to_php_sync():
    result = run_script("tools/cache_covers.py")

    assert result.returncode == 2
    assert "php bin/bangumi_covers.php sync --resume" in result.stderr
