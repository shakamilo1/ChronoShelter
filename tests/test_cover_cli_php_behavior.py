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


def test_import_mapping_does_not_touch_python_sqlite_and_rolls_back_on_failure(tmp_path):
    state = tmp_path / "state"
    covers = tmp_path / "covers"
    mapping = tmp_path / "mapping.jsonl"
    php = textwrap.dedent(f"""
    <?php
    error_reporting(E_ALL);
    set_error_handler(static function($severity, $message, $file, $line) {{
        throw new ErrorException($message, 0, $severity, $file, $line);
    }});
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    final class ImportFakeStatement {{
        public function __construct(private ImportFakeDb $db) {{}}
        public function execute($params = null): bool {{
            $this->db->executeCalls++;
            if ($this->db->failOnExecute > 0 && $this->db->executeCalls === $this->db->failOnExecute) {{ throw new RuntimeException('fake import write failed'); }}
            return true;
        }}
    }}
    final class ImportFakeDb {{
        public int $executeCalls = 0;
        public int $beginCalls = 0;
        public int $commitCalls = 0;
        public int $rollbackCalls = 0;
        public int $failOnExecute = 0;
        public function beginTransaction(): bool {{ $this->beginCalls++; return true; }}
        public function commit(): bool {{ $this->commitCalls++; return true; }}
        public function rollBack(): bool {{ $this->rollbackCalls++; return true; }}
        public function prepare(string $sql): ImportFakeStatement {{ return new ImportFakeStatement($this); }}
    }}
    ensure_runtime_dirs();
    $im = imagecreatetruecolor(1, 1);
    ob_start(); imagepng($im); $png = ob_get_clean();
    $makeRow = static function(int $id) use ($png) {{
        $name = $id . '_ok.png';
        $relative = cover_relative_path($id, $name);
        $absolute = cover_absolute_path($relative);
        if (!is_dir(dirname($absolute))) {{ mkdir(dirname($absolute), 0775, true); }}
        file_put_contents($absolute, $png);
        $meta = validate_image_file($absolute, 'image/png');
        db()->prepare("INSERT INTO cover_manifest (subject_id, subject_type, relative_path, remote_filename, mime_type, file_extension, file_size, sha256, artifact_status, deploy_status, status) VALUES (:id, 2, :path, :remote, :mime, :ext, :size, :sha, 'available', 'pending_deploy', 'pending_deploy')")
            ->execute(['id' => $id, 'path' => $relative, 'remote' => $name, 'mime' => $meta['mime_type'], 'ext' => $meta['extension'], 'size' => $meta['file_size'], 'sha' => $meta['sha256']]);
        return ['subject_id' => $id, 'status' => 'cached', 'remote_filename' => $name, 'source_url' => 'https://lain.bgm.tv/pic/cover/l/a/b/' . $name, 'local_path' => $relative, 'content_type' => $meta['mime_type'], 'file_size' => $meta['file_size'], 'sha256' => $meta['sha256'], 'updated_at' => '2026-07-23 00:00:00'];
    }};
    $row1 = $makeRow(7001);
    $row2 = $makeRow(7002);

    file_put_contents({json.dumps(str(mapping))}, json_encode($row1, JSON_UNESCAPED_SLASHES) . "\n" . json_encode($row2, JSON_UNESCAPED_SLASHES) . "\n");
    $fakeFail = new ImportFakeDb();
    $fakeFail->failOnExecute = 2;
    $GLOBALS['cover_sync_library_db'] = $fakeFail;
    $failError = null;
    try {{ import_mapping(['file' => {json.dumps(str(mapping))}]); }} catch (Throwable $e) {{ $failError = $e->getMessage(); }}
    $afterFail1 = manifest_row(7001)['deploy_status'];
    $afterFail2 = manifest_row(7002)['deploy_status'];

    $fakeOk = new ImportFakeDb();
    $GLOBALS['cover_sync_library_db'] = $fakeOk;
    $okStats = import_mapping(['file' => {json.dumps(str(mapping))}]);
    $afterOk1 = manifest_row(7001)['deploy_status'];
    $afterOk2 = manifest_row(7002)['deploy_status'];

    $badNoCover = {json.dumps(str(tmp_path / 'bad_no_cover.jsonl'))};
    file_put_contents($badNoCover, json_encode(['subject_id' => 8001, 'status' => 'no_cover', 'local_path' => 'subjects/000/008/8001_bad.png'], JSON_UNESCAPED_SLASHES) . "\n");
    $fakePrecheck = new ImportFakeDb();
    $GLOBALS['cover_sync_library_db'] = $fakePrecheck;
    $precheckError = null;
    try {{ import_mapping(['file' => $badNoCover]); }} catch (Throwable $e) {{ $precheckError = $e->getMessage(); }}

    echo json_encode([
        'fail_error' => $failError,
        'fail_rollback' => $fakeFail->rollbackCalls,
        'fail_commit' => $fakeFail->commitCalls,
        'after_fail' => [$afterFail1, $afterFail2],
        'ok_commits' => $fakeOk->commitCalls,
        'ok_stats' => $okStats['update_success'],
        'after_ok' => [$afterOk1, $afterOk2],
        'precheck_error' => $precheckError,
        'precheck_execute_calls' => $fakePrecheck->executeCalls,
    ], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {
        "CHRONOSHELTER_COVER_SYNC_STATE_DIR": str(state),
        "CHRONOSHELTER_COVERS_DIR": str(covers),
    })
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "fake import write failed" in data["fail_error"]
    assert data["fail_rollback"] == 1
    assert data["fail_commit"] == 0
    assert data["after_fail"] == ["pending_deploy", "pending_deploy"]
    assert data["ok_commits"] == 1
    assert data["ok_stats"] == 2
    assert data["after_ok"] == ["pending_deploy", "pending_deploy"]
    assert "no_cover mapping must not include file fields" in data["precheck_error"]
    assert data["precheck_execute_calls"] == 0
