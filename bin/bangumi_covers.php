#!/usr/bin/env php
<?php

declare(strict_types=1);

$root = dirname(__DIR__);
require_once $root . '/includes/database.php';

function cli_options(array $argv): array
{
    $command = $argv[1] ?? 'help';
    $options = ['file' => null];
    for ($i = 2; $i < count($argv); $i++) {
        $arg = $argv[$i];
        if (!str_starts_with($arg, '--')) continue;
        $arg = substr($arg, 2);
        [$key, $value] = array_pad(explode('=', $arg, 2), 2, null);
        if ($key === 'file') {
            $options['file'] = $value;
        } else {
            fwrite(STDERR, "Unknown option --{$key}\n");
            exit(2);
        }
    }
    return [$command, $options];
}

function cover_sync_paths(): array
{
    $root = dirname(__DIR__);
    return [
        'covers' => rtrim((string) getenv('CHRONOSHELTER_COVERS_DIR') ?: ($root . '/covers'), DIRECTORY_SEPARATOR),
    ];
}

function ensure_runtime_dirs(): void
{
    $covers = cover_sync_paths()['covers'];
    if (is_link($covers)) {
        throw new RuntimeException('covers root must not be a symlink');
    }
    if (!is_dir($covers) && !mkdir($covers, 0775, true) && !is_dir($covers)) {
        throw new RuntimeException('cannot create covers directory');
    }
}

function cover_partition_prefix(int $subjectId): string
{
    return 'subjects/' . sprintf('%03d', intdiv($subjectId, 1000000)) . '/' . sprintf('%03d', intdiv($subjectId % 1000000, 1000)) . '/';
}

function cover_relative_path(int $subjectId, string $filename): string
{
    if (!preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$/i', $filename)) {
        throw new RuntimeException('invalid cover filename');
    }
    return cover_partition_prefix($subjectId) . $filename;
}

function path_within_covers(string $absolute): bool
{
    $root = realpath(cover_sync_paths()['covers']);
    $real = realpath($absolute);
    return $root !== false && $real !== false && ($real === $root || str_starts_with($real, rtrim($root, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR));
}

function cover_absolute_path(string $relativePath): string
{
    $relativePath = str_replace('\\', '/', $relativePath);
    if ($relativePath === '' || str_starts_with($relativePath, '/') || str_contains($relativePath, '..') || preg_match('/[\x00-\x1f\x7f]/', $relativePath)) {
        throw new RuntimeException('unsafe cover path');
    }
    return cover_sync_paths()['covers'] . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relativePath);
}

function validate_image_file(string $path, string $expectedMime): array
{
    if (is_link($path) || !is_file($path) || !path_within_covers($path)) {
        throw new RuntimeException('image path is not a safe local file');
    }
    $size = filesize($path);
    if ($size === false || $size <= 0 || $size > 20 * 1024 * 1024) {
        throw new RuntimeException('invalid image file size');
    }
    $data = file_get_contents($path);
    if ($data === false || strlen($data) !== $size || preg_match('/^\s*[<{[]/', $data)) {
        throw new RuntimeException('invalid image content');
    }
    $mime = (new finfo(FILEINFO_MIME_TYPE))->file($path) ?: '';
    $expectedMime = strtolower(trim(explode(';', $expectedMime, 2)[0]));
    if ($expectedMime !== '' && $mime !== $expectedMime) {
        throw new RuntimeException('image MIME mismatch');
    }
    $ext = match ($mime) {
        'image/jpeg' => 'jpg',
        'image/png' => 'png',
        'image/webp' => 'webp',
        default => throw new RuntimeException('unsupported image MIME'),
    };
    $pathExt = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    if ($pathExt === 'jpeg') $pathExt = 'jpg';
    if ($pathExt !== $ext) {
        throw new RuntimeException('image extension mismatch');
    }
    if ($ext === 'jpg' && !(str_starts_with($data, "\xff\xd8") && str_ends_with($data, "\xff\xd9"))) {
        throw new RuntimeException('JPEG structure is incomplete');
    }
    if ($ext === 'png' && !str_contains($data, 'IEND')) {
        throw new RuntimeException('PNG structure is incomplete');
    }
    if ($ext === 'webp' && !(substr($data, 0, 4) === 'RIFF' && substr($data, 8, 4) === 'WEBP')) {
        throw new RuntimeException('WebP structure is incomplete');
    }
    $info = @getimagesize($path);
    if ($info === false || ($info[0] ?? 0) <= 0 || ($info[1] ?? 0) <= 0) {
        throw new RuntimeException('image dimensions are invalid');
    }
    $pixels = (int) $info[0] * (int) $info[1];
    if ($pixels <= 0 || $pixels > 50_000_000) {
        throw new RuntimeException('image dimensions exceed safety limit');
    }
    if (!function_exists('imagecreatefromstring')) {
        throw new RuntimeException('GD image decoder is required for import-mapping validation');
    }
    set_error_handler(static function($severity, $message, $file, $line) { throw new ErrorException($message, 0, $severity, $file, $line); });
    try {
        $image = imagecreatefromstring($data);
    } catch (Throwable $exc) {
        restore_error_handler();
        throw new RuntimeException('image decoder rejected file: ' . $exc->getMessage(), 0, $exc);
    }
    restore_error_handler();
    if ($image === false) {
        throw new RuntimeException('image decoder rejected file');
    }
    return ['mime_type' => $mime, 'extension' => $ext, 'file_size' => $size, 'sha256' => hash_file('sha256', $path)];
}

function import_mapping_row_is_safe(array $row): array
{
    $subjectId = (int) ($row['subject_id'] ?? 0);
    if ($subjectId <= 0 || (string) $subjectId !== (string) ($row['subject_id'] ?? '')) {
        throw new RuntimeException('invalid subject_id in mapping');
    }
    $status = (string) ($row['status'] ?? '');
    if (!in_array($status, ['cached', 'no_cover'], true)) {
        throw new RuntimeException('invalid import status for subject_id=' . $subjectId);
    }
    if ($status === 'no_cover') {
        foreach (['local_path', 'remote_filename', 'file_size', 'sha256', 'content_type', 'file_extension'] as $field) {
            if (isset($row[$field]) && $row[$field] !== null && $row[$field] !== '') {
                throw new RuntimeException('no_cover mapping must not include file fields for subject_id=' . $subjectId);
            }
        }
        return ['subject_id' => $subjectId, 'status' => 'no_cover', 'remote_filename' => null, 'source_url' => null, 'local_path' => null, 'content_type' => null, 'file_size' => null, 'sha256' => null, 'updated_at' => $row['updated_at'] ?? null];
    }
    $relativePath = (string) ($row['local_path'] ?? '');
    $remoteFilename = (string) ($row['remote_filename'] ?? '');
    if ($relativePath === '' || $remoteFilename === '') {
        throw new RuntimeException('cached mapping missing path fields for subject_id=' . $subjectId);
    }
    if (!preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$/i', $remoteFilename)) {
        throw new RuntimeException('unsafe remote_filename for subject_id=' . $subjectId);
    }
    $base = basename($relativePath);
    $prefix = cover_partition_prefix($subjectId);
    if (!str_starts_with(str_replace('\\', '/', $relativePath), $prefix) || !preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$/i', $base)) {
        throw new RuntimeException('mapped path does not match subject shard/name for subject_id=' . $subjectId);
    }
    $absolute = cover_absolute_path($relativePath);
    if (is_link($absolute) || !is_file($absolute) || !path_within_covers($absolute)) {
        throw new RuntimeException('mapped file missing or unsafe for subject_id=' . $subjectId);
    }
    if (!isset($row['file_size']) || filesize($absolute) !== (int) $row['file_size']) {
        throw new RuntimeException('mapped file size mismatch for subject_id=' . $subjectId);
    }
    if (empty($row['sha256']) || !preg_match('/^[a-f0-9]{64}$/i', (string) $row['sha256']) || hash_file('sha256', $absolute) !== strtolower((string) $row['sha256'])) {
        throw new RuntimeException('mapped file sha256 mismatch for subject_id=' . $subjectId);
    }
    $validated = validate_image_file($absolute, (string) ($row['content_type'] ?? ''));
    if ($validated['file_size'] !== (int) $row['file_size'] || $validated['sha256'] !== strtolower((string) $row['sha256'])) {
        throw new RuntimeException('mapped file metadata mismatch for subject_id=' . $subjectId);
    }
    $remoteExt = strtolower(pathinfo($remoteFilename, PATHINFO_EXTENSION));
    if ($remoteExt === 'jpeg') $remoteExt = 'jpg';
    if ($remoteExt !== $validated['extension']) {
        throw new RuntimeException('remote filename extension mismatch for subject_id=' . $subjectId);
    }
    return ['subject_id' => $subjectId, 'status' => 'cached', 'remote_filename' => $remoteFilename, 'source_url' => $row['source_url'] ?? null, 'local_path' => $relativePath, 'content_type' => $validated['mime_type'], 'file_size' => $validated['file_size'], 'sha256' => $validated['sha256'], 'updated_at' => $row['updated_at'] ?? null];
}

function cover_sync_library_db(): object
{
    if (isset($GLOBALS['cover_sync_library_db'])) return $GLOBALS['cover_sync_library_db'];
    if (function_exists('db_library')) return db_library();
    throw new RuntimeException('library database is not configured');
}

function import_mapping(array $options): array
{
    $file = $options['file'] ?? null;
    if (!$file || !is_file((string) $file)) throw new RuntimeException('--file is required for import-mapping');
    $rows = [];
    $seen = [];
    $handle = fopen((string) $file, 'rb');
    if ($handle === false) throw new RuntimeException('cannot open mapping file');
    while (($line = fgets($handle)) !== false) {
        $line = trim($line);
        if ($line === '') continue;
        $decoded = json_decode($line, true);
        if (!is_array($decoded)) { fclose($handle); throw new RuntimeException('invalid mapping JSON line'); }
        $row = import_mapping_row_is_safe($decoded);
        if (isset($seen[$row['subject_id']])) { fclose($handle); throw new RuntimeException('duplicate subject_id in mapping: ' . $row['subject_id']); }
        $seen[$row['subject_id']] = true;
        $rows[] = $row;
    }
    fclose($handle);
    $pdo = cover_sync_library_db();
    $pdo->beginTransaction();
    try {
        $stmt = $pdo->prepare('INSERT INTO cover_cache (subject_id, status, remote_filename, source_url, local_path, content_type, file_size, sha256, updated_at)
            VALUES (:subject_id, :status, :remote_filename, :source_url, :local_path, :content_type, :file_size, :sha256, COALESCE(:updated_at, CURRENT_TIMESTAMP))
            ON DUPLICATE KEY UPDATE status = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', status, VALUES(status)), remote_filename = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', remote_filename, VALUES(remote_filename)), source_url = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', source_url, VALUES(source_url)), local_path = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', local_path, VALUES(local_path)), content_type = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', content_type, VALUES(content_type)), file_size = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', file_size, VALUES(file_size)), sha256 = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', sha256, VALUES(sha256)), updated_at = VALUES(updated_at)');
        foreach ($rows as $row) $stmt->execute($row);
        $pdo->commit();
    } catch (Throwable $exc) {
        $pdo->rollBack();
        throw $exc;
    }
    return ['task' => 'import-mapping', 'update_success' => count($rows), 'complete' => true];
}

function usage(): void
{
    echo "Usage: php bin/bangumi_covers.php import-mapping --file=/path/to/cover-mapping.jsonl\n";
    echo "NAS/PHP does not sync Bangumi covers. Use Python for sync/verify/export.\n";
}

function main(array $argv): int
{
    [$command, $options] = cli_options($argv);
    try {
        ensure_runtime_dirs();
        if ($command === 'import-mapping') {
            foreach (import_mapping($options) as $key => $value) echo $key . ': ' . (string) $value . "\n";
            return 0;
        }
        if (in_array($command, ['sync','check-updates','apply-updates','retry-failed','deep-check','verify-files','export-mapping','cleanup-covers'], true)) {
            fwrite(STDERR, "PHP cover command is disabled on NAS; use Python sync/verify/export and PHP import-mapping only.\n");
            return 2;
        }
        usage();
        return 0;
    } catch (Throwable $exc) {
        fwrite(STDERR, 'ERROR: ' . $exc->getMessage() . "\n");
        return 1;
    }
}

if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) {
    exit(main($argv));
}
