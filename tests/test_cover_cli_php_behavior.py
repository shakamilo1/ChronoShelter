import json
import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_php(code: str, env: dict | None = None):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = subprocess.run(
        ["php"],
        input=code,
        text=True,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
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


def test_apply_one_failure_paths_cleanup_temp_and_preserve_deploy_state(tmp_path):
    state = tmp_path / "state"
    covers = tmp_path / "covers"
    php = textwrap.dedent(f"""
    <?php
    error_reporting(E_ALL);
    set_error_handler(static function($severity, $message, $file, $line) {{
        throw new ErrorException($message, 0, $severity, $file, $line);
    }});
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $GLOBALS['cover_sync_options'] = ['write-mysql' => false];
    $GLOBALS['cover_sync_sleep'] = static function($seconds) {{}};
    ensure_runtime_dirs();
    $im = imagecreatetruecolor(1, 1);
    ob_start();
    imagepng($im);
    $png = ob_get_clean();
    $cases = [];
    $tmpDir = cover_sync_paths()['tmp'];
    $emptyTmp = static function() use ($tmpDir) {{
        $left = glob($tmpDir . '/*');
        return $left === false ? [] : array_map('basename', $left);
    }};

    db()->prepare("INSERT INTO cover_manifest (subject_id, subject_type, observed_url, downloaded_url, relative_path, remote_filename, sha256, file_size, mime_type, file_extension, artifact_status, deploy_status, status) VALUES (1234, 2, 'https://lain.bgm.tv/pic/cover/l/a/b/1234_wrong.jpg', 'old-url', 'subjects/000/001/1234_old.png', '1234_old.png', :sha, 90, 'image/png', 'png', 'available', 'pending_deploy', 'pending_update')")
        ->execute(['sha' => str_repeat('a', 64)]);
    $GLOBALS['cover_sync_http_transport'] = static function($url, $headers, $timeout) use ($png) {{
        return ['status' => 200, 'headers' => ['content-type' => 'image/png'], 'body' => $png, 'final_url' => $url];
    }};
    $result = apply_one(1234);
    $row = manifest_row(1234);
    $cases['bad_filename'] = ['result' => $result, 'tmp' => $emptyTmp(), 'deploy' => $row['deploy_status'], 'path' => $row['relative_path']];

    db()->prepare("INSERT INTO cover_manifest (subject_id, subject_type, observed_url, artifact_status, deploy_status, status) VALUES (2345, 2, 'https://lain.bgm.tv/img/no_icon_subject.png', 'missing', 'pending_deploy', 'pending')")->execute();
    $GLOBALS['cover_sync_http_transport'] = static function($url, $headers, $timeout) {{
        return ['status' => 200, 'headers' => ['content-type' => 'image/png'], 'body' => 'nope', 'final_url' => 'https://lain.bgm.tv/img/no_icon_subject.png'];
    }};
    $result = apply_one(2345);
    $row = manifest_row(2345);
    $cases['no_icon'] = ['result' => $result, 'tmp' => $emptyTmp(), 'artifact' => $row['artifact_status'], 'check' => $row['last_check_result'], 'path' => $row['relative_path']];

    db()->prepare("INSERT INTO cover_manifest (subject_id, subject_type, observed_url, downloaded_url, relative_path, remote_filename, sha256, file_size, mime_type, file_extension, artifact_status, deploy_status, status) VALUES (3456, 2, 'https://lain.bgm.tv/pic/cover/l/a/b/3456_new.png', 'old-url', 'subjects/000/003/3456_old.png', '3456_old.png', :sha, 90, 'image/png', 'png', 'available', 'mapping_failed', 'pending_update')")
        ->execute(['sha' => str_repeat('b', 64)]);
    $GLOBALS['cover_sync_http_transport'] = static function($url, $headers, $timeout) use ($png) {{
        return ['status' => 200, 'headers' => ['content-type' => 'image/png'], 'body' => $png, 'final_url' => $url];
    }};
    $GLOBALS['cover_sync_options'] = ['write-mysql' => true];
    $result = apply_one(3456);
    $row = manifest_row(3456);
    $cases['mysql_fail'] = ['result' => $result, 'tmp' => $emptyTmp(), 'deploy' => $row['deploy_status'], 'path' => $row['relative_path'], 'new_file_exists' => is_file(cover_absolute_path($row['relative_path']))];

    echo json_encode($cases, JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {
        "CHRONOSHELTER_COVER_SYNC_STATE_DIR": str(state),
        "CHRONOSHELTER_COVERS_DIR": str(covers),
    })
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["bad_filename"]["result"] is False
    assert data["bad_filename"]["tmp"] == []
    assert data["bad_filename"]["deploy"] == "pending_deploy"
    assert data["bad_filename"]["path"] == "subjects/000/001/1234_old.png"
    assert data["no_icon"]["result"] is False
    assert data["no_icon"]["tmp"] == []
    assert data["no_icon"]["artifact"] == "missing"
    assert data["no_icon"]["check"] == "remote_missing"
    assert data["no_icon"]["path"] is None
    assert data["mysql_fail"]["result"] is False
    assert data["mysql_fail"]["tmp"] == []
    assert data["mysql_fail"]["deploy"] == "mapping_failed"
    assert data["mysql_fail"]["new_file_exists"] is True


def test_verify_files_reports_local_invalid_without_changing_deploy_status(tmp_path):
    state = tmp_path / "state"
    covers = tmp_path / "covers"
    php = textwrap.dedent(f"""
    <?php
    error_reporting(E_ALL);
    set_error_handler(static function($severity, $message, $file, $line) {{
        throw new ErrorException($message, 0, $severity, $file, $line);
    }});
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    ensure_runtime_dirs();
    $relative = cover_relative_path(491569, '491569_bad.png');
    $absolute = cover_absolute_path($relative);
    mkdir(dirname($absolute), 0775, true);
    file_put_contents($absolute, "not an image");
    db()->prepare("INSERT INTO cover_manifest (subject_id, subject_type, relative_path, remote_filename, mime_type, file_extension, file_size, sha256, artifact_status, deploy_status, status) VALUES (491569, 2, :path, '491569_bad.png', 'image/png', 'png', 12, :sha, 'available', 'pending_deploy', 'pending_deploy')")
        ->execute(['path' => $relative, 'sha' => str_repeat('0', 64)]);
    $stats = verify_files([]);
    $row = manifest_row(491569);
    echo json_encode(['stats' => $stats, 'deploy' => $row['deploy_status'], 'artifact' => $row['artifact_status'], 'check' => $row['last_check_result']], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {
        "CHRONOSHELTER_COVER_SYNC_STATE_DIR": str(state),
        "CHRONOSHELTER_COVERS_DIR": str(covers),
    })
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["stats"]["complete"] is False
    assert data["stats"]["update_failed"] == 1
    assert data["deploy"] == "pending_deploy"
    assert data["artifact"] == "invalid"
    assert data["check"] == "local_invalid"


def test_check_updates_resume_cursor_and_empty_page_failure(tmp_path):
    state = tmp_path / "state"
    covers = tmp_path / "covers"
    php = textwrap.dedent(f"""
    <?php
    error_reporting(E_ALL);
    set_error_handler(static function($severity, $message, $file, $line) {{
        throw new ErrorException($message, 0, $severity, $file, $line);
    }});
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $GLOBALS['cover_sync_sleep'] = static function($seconds) {{}};
    $GLOBALS['cover_sync_options'] = ['write-mysql' => false];
    $seen = [];
    $GLOBALS['cover_sync_http_transport'] = function($url, $headers, $timeout) use (&$seen) {{
        parse_str(parse_url($url, PHP_URL_QUERY), $q);
        $offset = (int) $q['offset'];
        $seen[] = $offset;
        $data = [];
        for ($i = $offset; $i < min(50, $offset + 50); $i++) {{
            $data[] = ['id' => 100000 + $i, 'type' => 2, 'images' => null];
        }}
        return ['status' => 200, 'headers' => ['content-type' => 'application/json'], 'body' => json_encode(['total' => 50, 'limit' => 50, 'offset' => $offset, 'data' => $data]), 'final_url' => $url];
    }};
    $options = ['resume' => false, 'max-pages' => null, 'max-items' => 10, 'dry-run' => true, 'api-delay' => 0, 'download-delay' => 0];
    $first = scan_pages('check-updates', $options);
    $options['resume'] = true;
    $options['max-items'] = 40;
    $second = scan_pages('check-updates', $options);
    $run = db()->query("SELECT next_offset FROM sync_runs WHERE run_type = 'check-updates' ORDER BY updated_at DESC LIMIT 1")->fetchColumn();
    $GLOBALS['cover_sync_http_transport'] = static function($url, $headers, $timeout) {{
        return ['status' => 200, 'headers' => [], 'body' => json_encode(['total' => 2, 'limit' => 50, 'offset' => 0, 'data' => []]), 'final_url' => $url];
    }};
    $emptyError = null;
    try {{ fetch_subject_page(0); }} catch (Throwable $e) {{ $emptyError = $e->getMessage(); }}
    echo json_encode(['seen' => $seen, 'first' => $first['next_offset'], 'second' => $second['next_offset'], 'run' => (int) $run, 'empty_error' => $emptyError], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {
        "CHRONOSHELTER_COVER_SYNC_STATE_DIR": str(state),
        "CHRONOSHELTER_COVERS_DIR": str(covers),
    })
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["seen"] == [0, 10]
    assert data["first"] == 10
    assert data["second"] == 50
    assert data["run"] == 50
    assert "empty data" in data["empty_error"]
