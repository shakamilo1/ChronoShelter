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
    return subprocess.run(["php"], input=code, text=True, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full_env, check=False)


def test_truncated_jpeg_is_rejected_by_php_validator(tmp_path):
    covers = tmp_path / "covers"
    image = covers / "bad.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"\xff\xd8\xff\xe0" + b"broken")
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $error = null;
    try {{ validate_image_file({json.dumps(str(image))}, 'image/jpeg'); }} catch (Throwable $e) {{ $error = $e->getMessage(); }}
    echo json_encode(['error' => $error], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(covers)})
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["error"] is not None


def test_import_mapping_rolls_back_and_does_not_open_python_sqlite(tmp_path):
    covers = tmp_path / "covers"
    mapping = tmp_path / "mapping.jsonl"
    php = textwrap.dedent(f"""
    <?php
    error_reporting(E_ALL);
    set_error_handler(static function($severity, $message, $file, $line) {{ throw new ErrorException($message, 0, $severity, $file, $line); }});
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
        public int $executeCalls = 0; public int $beginCalls = 0; public int $commitCalls = 0; public int $rollbackCalls = 0; public int $failOnExecute = 0;
        public function beginTransaction(): bool {{ $this->beginCalls++; return true; }}
        public function commit(): bool {{ $this->commitCalls++; return true; }}
        public function rollBack(): bool {{ $this->rollbackCalls++; return true; }}
        public function prepare(string $sql): ImportFakeStatement {{ return new ImportFakeStatement($this); }}
    }}
    ensure_runtime_dirs();
    $im = imagecreatetruecolor(1, 1); ob_start(); imagepng($im); $png = ob_get_clean();
    $makeRow = static function(int $id) use ($png) {{
        $name = $id . '_ok.png';
        $relative = cover_relative_path($id, $name);
        $absolute = cover_absolute_path($relative);
        if (!is_dir(dirname($absolute))) {{ mkdir(dirname($absolute), 0775, true); }}
        file_put_contents($absolute, $png);
        $meta = validate_image_file($absolute, 'image/png');
        return ['subject_id' => $id, 'status' => 'cached', 'remote_filename' => $name, 'source_url' => 'https://lain.bgm.tv/pic/cover/l/a/b/' . $name, 'local_path' => $relative, 'content_type' => $meta['mime_type'], 'file_size' => $meta['file_size'], 'sha256' => $meta['sha256'], 'updated_at' => '2026-07-23 00:00:00'];
    }};
    file_put_contents({json.dumps(str(mapping))}, json_encode($makeRow(7001), JSON_UNESCAPED_SLASHES) . "\n" . json_encode($makeRow(7002), JSON_UNESCAPED_SLASHES) . "\n");
    $fakeFail = new ImportFakeDb(); $fakeFail->failOnExecute = 2; $GLOBALS['cover_sync_library_db'] = $fakeFail;
    $failError = null; try {{ import_mapping(['file' => {json.dumps(str(mapping))}]); }} catch (Throwable $e) {{ $failError = $e->getMessage(); }}
    $sqliteExistsAfterFail = file_exists({json.dumps(str(tmp_path / 'state' / 'covers.sqlite'))});
    $fakeOk = new ImportFakeDb(); $GLOBALS['cover_sync_library_db'] = $fakeOk; $okStats = import_mapping(['file' => {json.dumps(str(mapping))}]);
    $badNoCover = {json.dumps(str(tmp_path / 'bad_no_cover.jsonl'))};
    file_put_contents($badNoCover, json_encode(['subject_id' => 8001, 'status' => 'no_cover', 'local_path' => 'subjects/000/008/8001_bad.png'], JSON_UNESCAPED_SLASHES) . "\n");
    $fakePrecheck = new ImportFakeDb(); $GLOBALS['cover_sync_library_db'] = $fakePrecheck; $precheckError = null;
    try {{ import_mapping(['file' => $badNoCover]); }} catch (Throwable $e) {{ $precheckError = $e->getMessage(); }}
    echo json_encode(['fail_error' => $failError, 'fail_rollback' => $fakeFail->rollbackCalls, 'fail_commit' => $fakeFail->commitCalls, 'ok_commits' => $fakeOk->commitCalls, 'ok_stats' => $okStats['update_success'], 'precheck_error' => $precheckError, 'precheck_execute_calls' => $fakePrecheck->executeCalls, 'sqlite_exists' => $sqliteExistsAfterFail], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(covers), "CHRONOSHELTER_COVER_SYNC_STATE_DIR": str(tmp_path / "state")})
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "fake import write failed" in data["fail_error"]
    assert data["fail_rollback"] == 1
    assert data["fail_commit"] == 0
    assert data["ok_commits"] == 1
    assert data["ok_stats"] == 2
    assert "no_cover mapping must not include file fields" in data["precheck_error"]
    assert data["precheck_execute_calls"] == 0
    assert data["sqlite_exists"] is False


def test_old_php_commands_are_disabled(tmp_path):
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $code = main(['bin/bangumi_covers.php', 'sync']);
    echo json_encode(['code' => $code]);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(tmp_path / "covers")})
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["code"] == 2
    assert "disabled on NAS" in proc.stderr


def test_php_import_validator_rejects_external_path_and_corrupt_png(tmp_path):
    covers = tmp_path / "covers"
    outside = tmp_path / "outside.png"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-complete-png")
    corrupt = covers / "subjects" / "000" / "009" / "9001_bad.png"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-complete-png")
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $errors = [];
    foreach ([{json.dumps(str(outside))}, {json.dumps(str(corrupt))}] as $path) {{
        try {{ validate_image_file($path, 'image/png'); $errors[] = null; }} catch (Throwable $e) {{ $errors[] = $e->getMessage(); }}
    }}
    echo json_encode($errors, JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(covers)})
    assert proc.returncode == 0, proc.stderr
    errors = json.loads(proc.stdout)
    assert "safe local file" in errors[0]
    assert errors[1] is not None


def test_php_import_validator_rejects_parent_symlink(tmp_path):
    covers = tmp_path / "covers"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    parent = covers / "subjects" / "000" / "010"
    parent.parent.mkdir(parents=True)
    parent.symlink_to(outside, target_is_directory=True)
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    $error = null;
    try {{ import_mapping_row_is_safe(['subject_id' => '10001', 'status' => 'cached', 'remote_filename' => '10001_bad.png', 'local_path' => 'subjects/000/010/10001_bad.png', 'content_type' => 'image/png', 'file_size' => 1, 'sha256' => str_repeat('0', 64)]); }} catch (Throwable $e) {{ $error = $e->getMessage(); }}
    echo json_encode(['error' => $error], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(covers)})
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["error"] is not None


def test_php_cover_sync_uses_project_db_library_function():
    source = (ROOT / "bin" / "bangumi_covers.php").read_text(encoding="utf-8")
    assert "db_library()" in source
    assert "return library_db()" not in source


def test_php_import_mapping_upserts_real_jsonl_fields(tmp_path):
    covers = tmp_path / "covers"
    mapping = tmp_path / "mapping.jsonl"
    php = textwrap.dedent(f"""
    <?php
    require {json.dumps(str(ROOT / 'bin' / 'bangumi_covers.php'))};
    final class CapturingStatement {{
        public function __construct(private CapturingDb $db) {{}}
        public function execute($params = null): bool {{
            $this->db->rows[(int)$params['subject_id']] = $params;
            $this->db->executeCalls++;
            return true;
        }}
    }}
    final class CapturingDb {{
        public array $rows = []; public int $executeCalls = 0; public int $beginCalls = 0; public int $commitCalls = 0; public int $rollbackCalls = 0;
        public function beginTransaction(): bool {{ $this->beginCalls++; return true; }}
        public function commit(): bool {{ $this->commitCalls++; return true; }}
        public function rollBack(): bool {{ $this->rollbackCalls++; return true; }}
        public function prepare(string $sql): CapturingStatement {{ return new CapturingStatement($this); }}
    }}
    ensure_runtime_dirs();
    $im = imagecreatetruecolor(1, 1); ob_start(); imagepng($im); $png = ob_get_clean();
    $name = '9001_ok.png'; $relative = cover_relative_path(9001, $name); $absolute = cover_absolute_path($relative);
    if (!is_dir(dirname($absolute))) {{ mkdir(dirname($absolute), 0775, true); }}
    file_put_contents($absolute, $png); $meta = validate_image_file($absolute, 'image/png');
    $row = ['subject_id' => 9001, 'status' => 'cached', 'remote_filename' => $name, 'source_url' => 'https://lain.bgm.tv/pic/cover/l/a/b/' . $name, 'local_path' => $relative, 'content_type' => $meta['mime_type'], 'file_size' => $meta['file_size'], 'sha256' => $meta['sha256'], 'updated_at' => '2026-07-24 00:00:00'];
    file_put_contents({json.dumps(str(mapping))}, json_encode($row, JSON_UNESCAPED_SLASHES) . "\n");
    $db = new CapturingDb(); $GLOBALS['cover_sync_library_db'] = $db;
    $first = import_mapping(['file' => {json.dumps(str(mapping))}]);
    $row['source_url'] = 'https://lain.bgm.tv/pic/cover/l/a/b/' . $name . '?v=2';
    file_put_contents({json.dumps(str(mapping))}, json_encode($row, JSON_UNESCAPED_SLASHES) . "\n");
    $second = import_mapping(['file' => {json.dumps(str(mapping))}]);
    echo json_encode(['first' => $first['update_success'], 'second' => $second['update_success'], 'executeCalls' => $db->executeCalls, 'rowCount' => count($db->rows), 'row' => $db->rows[9001], 'commits' => $db->commitCalls], JSON_UNESCAPED_SLASHES);
    ?>
    """)
    proc = run_php(php, {"CHRONOSHELTER_COVERS_DIR": str(covers)})
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["first"] == 1
    assert data["second"] == 1
    assert data["executeCalls"] == 2
    assert data["rowCount"] == 1
    row = data["row"]
    for key in ["subject_id", "status", "remote_filename", "local_path", "updated_at"]:
        assert key in row
    assert row["subject_id"] == 9001
    assert row["status"] == "cached"
    assert row["remote_filename"] == "9001_ok.png"
    assert row["local_path"] == "subjects/000/009/9001_ok.png"
    assert "source_url" not in row
    assert "content_type" not in row
    assert "file_size" not in row
    assert "sha256" not in row
    assert data["commits"] == 2
