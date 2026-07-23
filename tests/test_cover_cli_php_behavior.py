import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_php(code: str):
    proc = subprocess.run(
        ["php"],
        input=code,
        text=True,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc


def test_api_token_is_scoped_to_api_host_and_redirect_is_refused_without_leaking_to_next_host():
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    putenv('BANGUMI_ACCESS_TOKEN=fake-test-token');
    $seen = [];
    $GLOBALS['cover_sync_http_transport'] = function ($url, $headers, $timeout) use (&$seen) {{
        $seen[] = ['url' => $url, 'headers' => $headers];
        return ['status' => 302, 'headers' => ['location' => 'https://evil.example/steal'], 'body' => '', 'final_url' => $url];
    }};
    $error = null;
    try {{ fetch_subject_page(0); }} catch (Throwable $e) {{ $error = $e->getMessage(); }}
    echo json_encode(['seen' => $seen, 'error' => $error], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "redirect refused" in data["error"]
    assert len(data["seen"]) == 1
    assert data["seen"][0]["url"].startswith("https://api.bgm.tv/")
    assert any(h == "Authorization: Bearer fake-test-token" for h in data["seen"][0]["headers"])
    assert "fake-test-token" not in data["error"]


def test_image_redirects_never_send_authorization_and_report_final_url():
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    putenv('BANGUMI_ACCESS_TOKEN=fake-test-token');
    $seen = [];
    $GLOBALS['cover_sync_http_transport'] = function ($url, $headers, $timeout) use (&$seen) {{
        $seen[] = ['url' => $url, 'headers' => $headers];
        if (count($seen) === 1) {{
            return ['status' => 302, 'headers' => ['location' => 'https://cdn.example/491569_x.jpg'], 'body' => '', 'final_url' => $url];
        }}
        return ['status' => 200, 'headers' => ['content-type' => 'image/jpeg'], 'body' => 'not-used', 'final_url' => $url];
    }};
    $response = http_request_follow_image_redirects('https://lain.bgm.tv/pic/cover/l/a/b/491569_x.jpg', ['If-None-Match: abc'], 1);
    echo json_encode(['seen' => $seen, 'final_url' => $response['final_url']], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["final_url"] == "https://cdn.example/491569_x.jpg"
    assert len(data["seen"]) == 2
    for request in data["seen"]:
        assert not any("Authorization:" in h for h in request["headers"])
        assert any(h == "If-None-Match: abc" for h in request["headers"])


def test_truncated_jpeg_is_rejected_by_php_validator(tmp_path):
    image = tmp_path / "bad.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"broken")
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $error = null;
    try {{ validate_image_file({json.dumps(str(image))}, 'image/jpeg'); }} catch (Throwable $e) {{ $error = $e->getMessage(); }}
    echo json_encode(['error' => $error], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["error"] is not None


def test_api_rejects_userinfo_and_non_443_port_before_authorization_header():
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    putenv('BANGUMI_ACCESS_TOKEN=fake-test-token');
    $results = [];
    foreach (['https://api.bgm.tv@evil.example/v0/subjects', 'https://api.bgm.tv:444/v0/subjects', 'http://api.bgm.tv/v0/subjects'] as $url) {{
        try {{ api_request_headers($url); $results[] = 'allowed'; }} catch (Throwable $e) {{ $results[] = $e->getMessage(); }}
    }}
    echo json_encode($results, JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout)
    assert all("refusing to send" in item for item in results)
    assert "fake-test-token" not in proc.stdout + proc.stderr


def test_image_request_headers_filter_caller_supplied_authorization():
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    putenv('BANGUMI_ACCESS_TOKEN=fake-test-token');
    echo json_encode(image_request_headers(['Authorization: Bearer injected', 'If-Modified-Since: Wed, 01 Jan 2025 00:00:00 GMT']), JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    headers = json.loads(proc.stdout)
    assert not any(h.lower().startswith('authorization:') for h in headers)
    assert any(h.startswith('If-Modified-Since:') for h in headers)
    assert not any('image/avif' in h for h in headers)


def test_retry_policy_retries_429_and_not_ordinary_404():
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $calls = 0;
    $slept = [];
    $GLOBALS['cover_sync_sleep'] = function ($seconds) use (&$slept) {{ $slept[] = $seconds; }};
    $GLOBALS['cover_sync_http_transport'] = function ($url, $headers, $timeout) use (&$calls) {{
        $calls++;
        if ($calls < 3) {{ return ['status' => 429, 'headers' => ['retry-after' => '1'], 'body' => '', 'final_url' => $url]; }}
        return ['status' => 200, 'headers' => [], 'body' => '{{}}', 'final_url' => $url];
    }};
    http_request('https://api.bgm.tv/v0/subjects', []);
    $firstCalls = $calls;
    $calls = 0;
    $GLOBALS['cover_sync_http_transport'] = function ($url, $headers, $timeout) use (&$calls) {{ $calls++; return ['status' => 404, 'headers' => [], 'body' => '', 'final_url' => $url]; }};
    http_request('https://api.bgm.tv/v0/missing', []);
    echo json_encode(['retry_calls' => $firstCalls, 'not_retry_calls' => $calls, 'sleeps' => count($slept)], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data == {'retry_calls': 3, 'not_retry_calls': 1, 'sleeps': 2}
