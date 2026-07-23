#!/usr/bin/env php
<?php

declare(strict_types=1);

const BANGUMI_COVER_USER_AGENT = 'shakamilo1/ChronoShelter-cover-sync/1.0 (https://github.com/shakamilo1/ChronoShelter)';
const BANGUMI_SUBJECTS_API = 'https://api.bgm.tv/v0/subjects';
const SUBJECT_TYPE_ANIME = 2;
const PAGE_LIMIT = 50;
const STATUSES = ['pending', 'downloading', 'downloaded', 'unchanged', 'pending_update', 'no_cover', 'remote_missing', 'failed', 'mapping_failed', 'pending_deploy'];

class RemoteMissingCover extends RuntimeException {}

$root = dirname(__DIR__);
require_once $root . '/includes/database.php';

function cli_options(array $argv): array
{
    $command = $argv[1] ?? 'help';
    $options = [
        'resume' => false,
        'download-delay' => 1.0,
        'api-delay' => 1.0,
        'concurrency' => 1,
        'max-pages' => null,
        'max-items' => null,
        'subject-id' => null,
        'sample' => null,
        'dry-run' => false,
        'force' => false,
        'verbose' => false,
        'retry-failed' => false,
        'all' => false,
        'confirm-all' => false,
        'prune-remote-missing' => false,
        'file' => null,
        'write-mysql' => false,
        'apply' => false,
    ];
    for ($i = 2; $i < count($argv); $i++) {
        $arg = $argv[$i];
        if (!str_starts_with($arg, '--')) {
            continue;
        }
        $arg = substr($arg, 2);
        [$key, $value] = array_pad(explode('=', $arg, 2), 2, null);
        if (!array_key_exists($key, $options)) {
            fwrite(STDERR, "Unknown option --{$key}\n");
            exit(2);
        }
        if (is_bool($options[$key])) {
            $options[$key] = $value === null ? true : filter_var($value, FILTER_VALIDATE_BOOLEAN);
        } elseif (in_array($key, ['max-pages', 'max-items', 'subject-id', 'sample'], true)) {
            $options[$key] = $value === null ? null : max(0, (int) $value);
        } elseif ($key === 'file') {
            $options[$key] = $value;
        } else {
            $options[$key] = $value === null ? $options[$key] : (float) $value;
        }
    }
    $options['concurrency'] = 1; // conservative implementation: accepted for compatibility, intentionally serial.
    return [$command, $options];
}

function now_utc(): string
{
    return gmdate('Y-m-d H:i:s');
}

function cover_sync_paths(): array
{
    $config = app_config()['covers'] ?? [];
    $coversDir = rtrim((string) (getenv('CHRONOSHELTER_COVERS_DIR') ?: ($config['directory'] ?? dirname(__DIR__) . '/covers')), "/\\");
    $stateDir = rtrim((string) (getenv('CHRONOSHELTER_COVER_SYNC_STATE_DIR') ?: dirname(__DIR__) . '/var/cover-sync'), "/\\");
    return [
        'covers' => $coversDir,
        'subjects' => trim((string) ($config['subjects_directory'] ?? 'subjects'), '/'),
        'state' => $stateDir,
        'tmp' => $stateDir . '/tmp',
        'logs' => $stateDir . '/logs',
        'reports' => $stateDir . '/reports',
        'sqlite' => $stateDir . '/covers.sqlite',
    ];
}

function ensure_runtime_dirs(): void
{
    foreach (['state', 'tmp', 'logs', 'reports'] as $key) {
        $dir = cover_sync_paths()[$key];
        if (!is_dir($dir) && !mkdir($dir, 0775, true) && !is_dir($dir)) {
            throw new RuntimeException("Cannot create {$dir}");
        }
    }
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    ensure_runtime_dirs();
    $pdo = new PDO('sqlite:' . cover_sync_paths()['sqlite']);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('CREATE TABLE IF NOT EXISTS cover_manifest (
        subject_id INTEGER PRIMARY KEY,
        subject_type INTEGER NOT NULL DEFAULT 2,
        downloaded_url TEXT NULL,
        observed_url TEXT NULL,
        remote_filename TEXT NULL,
        relative_path TEXT NULL,
        mime_type TEXT NULL,
        file_extension TEXT NULL,
        file_size INTEGER NULL,
        sha256 TEXT NULL,
        etag TEXT NULL,
        last_modified TEXT NULL,
        status TEXT NOT NULL DEFAULT \'pending\',
        last_seen_at TEXT NULL,
        last_checked_at TEXT NULL,
        last_downloaded_at TEXT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT NULL,
        artifact_status TEXT NULL,
        deploy_status TEXT NULL,
        last_check_result TEXT NULL,
        last_error TEXT NULL,
        checked_at TEXT NULL,
        last_success_at TEXT NULL
    )');
    foreach ([
        'remote_filename TEXT NULL',
        'artifact_status TEXT NULL',
        'deploy_status TEXT NULL',
        'last_check_result TEXT NULL',
        'last_error TEXT NULL',
        'checked_at TEXT NULL',
        'last_success_at TEXT NULL',
    ] as $columnSql) {
        try {
            $pdo->exec('ALTER TABLE cover_manifest ADD COLUMN ' . $columnSql);
        } catch (Throwable) {
            // Column already exists.
        }
    }
    $pdo->exec("UPDATE cover_manifest
        SET artifact_status = CASE
                WHEN relative_path IS NOT NULL AND relative_path <> '' THEN 'available'
                WHEN status = 'no_cover' THEN 'missing'
                ELSE COALESCE(artifact_status, 'missing')
            END
        WHERE artifact_status IS NULL");
    $pdo->exec("UPDATE cover_manifest
        SET deploy_status = CASE
                WHEN status = 'mapping_failed' THEN 'mapping_failed'
                WHEN status = 'pending_deploy' THEN 'pending_deploy'
                WHEN status IN ('downloaded', 'unchanged') AND relative_path IS NOT NULL AND relative_path <> '' THEN 'deployed'
                ELSE COALESCE(deploy_status, 'pending_deploy')
            END
        WHERE deploy_status IS NULL");
    $pdo->exec("UPDATE cover_manifest
        SET last_check_result = CASE
                WHEN status = 'remote_missing' THEN 'remote_missing'
                WHEN status = 'failed' THEN 'http_failed'
                WHEN status = 'pending_update' THEN 'updated'
                WHEN status = 'unchanged' THEN 'unchanged'
                ELSE COALESCE(last_check_result, status)
            END
        WHERE last_check_result IS NULL");
    $pdo->exec('CREATE TABLE IF NOT EXISTS sync_runs (
        run_id TEXT PRIMARY KEY,
        run_type TEXT NOT NULL,
        next_offset INTEGER NOT NULL DEFAULT 0,
        total INTEGER NULL,
        started_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT NULL,
        run_status TEXT NOT NULL
    )');
    return $pdo;
}

function cover_partition_prefix(int $subjectId): string
{
    $level1 = str_pad((string) intdiv($subjectId, 1000000), 3, '0', STR_PAD_LEFT);
    $level2 = str_pad((string) intdiv($subjectId % 1000000, 1000), 3, '0', STR_PAD_LEFT);
    return 'subjects/' . $level1 . '/' . $level2 . '/';
}

function safe_remote_filename(int $subjectId, string $url, string $detectedExtension): string
{
    $path = parse_url($url, PHP_URL_PATH);
    $basename = is_string($path) ? rawurldecode(basename($path)) : '';
    if (preg_match('#[\\\\/]|\.\.|[\x00-\x1F\x7F]#', $basename)) {
        $basename = '';
    }
    if (preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$/i', $basename, $m)) {
        $ext = strtolower($m[1]) === 'jpeg' ? 'jpg' : strtolower($m[1]);
        if ($ext === $detectedExtension) {
            return $basename;
        }
        throw new RuntimeException('remote filename extension does not match detected image type');
    }
    return $subjectId . '_' . substr(hash('sha256', $url), 0, 12) . '.' . $detectedExtension;
}

function cover_relative_path(int $subjectId, string $filename): string
{
    if ($subjectId <= 0 || !preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$/i', $filename)) {
        throw new InvalidArgumentException('invalid cover filename');
    }
    return cover_partition_prefix($subjectId) . $filename;
}

function cover_absolute_path(string $relativePath): string
{
    if (!preg_match('#^subjects/[0-9]{3,}/[0-9]{3}/[0-9]+_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$#i', $relativePath)
        && !preg_match('#^[0-9]+\.(jpg|jpeg|png|webp)$#i', $relativePath)) {
        throw new InvalidArgumentException('unsafe relative cover path');
    }
    return cover_sync_paths()['covers'] . '/' . $relativePath;
}

function normalized_url_host(string $url): ?string
{
    $host = parse_url($url, PHP_URL_HOST);
    if (!is_string($host) || $host === '') {
        return null;
    }
    return strtolower(rtrim($host, '.'));
}

function api_request_headers(string $url): array
{
    $scheme = strtolower((string) parse_url($url, PHP_URL_SCHEME));
    $host = normalized_url_host($url);
    $user = parse_url($url, PHP_URL_USER);
    $pass = parse_url($url, PHP_URL_PASS);
    $port = parse_url($url, PHP_URL_PORT);
    if ($scheme !== 'https' || $host !== 'api.bgm.tv' || $user !== null || $pass !== null || ($port !== null && (int) $port !== 443)) {
        throw new RuntimeException('refusing to send Bangumi API request outside https://api.bgm.tv');
    }
    $headers = ['User-Agent: ' . BANGUMI_COVER_USER_AGENT, 'Accept: application/json'];
    $token = getenv('BANGUMI_ACCESS_TOKEN') ?: '';
    if ($token !== '') {
        $headers[] = 'Authorization: Bearer ' . $token;
    }
    return $headers;
}

function image_request_headers(array $conditionalHeaders = []): array
{
    $safeConditional = [];
    foreach ($conditionalHeaders as $header) {
        if (!is_string($header) || preg_match('/^\s*Authorization\s*:/i', $header)) {
            continue;
        }
        $safeConditional[] = $header;
    }
    return array_merge([
        'User-Agent: ' . BANGUMI_COVER_USER_AGENT,
        'Accept: image/webp,image/png,image/jpeg,*/*;q=0.8',
    ], $safeConditional);
}

function cover_sync_sleep(float $seconds): void
{
    if (isset($GLOBALS['cover_sync_sleep']) && is_callable($GLOBALS['cover_sync_sleep'])) {
        ($GLOBALS['cover_sync_sleep'])($seconds);
        return;
    }
    usleep((int) max(0, $seconds * 1000000));
}

function http_request_once(string $url, array $headers, int $timeout = 30): array
{
    if (isset($GLOBALS['cover_sync_http_transport']) && is_callable($GLOBALS['cover_sync_http_transport'])) {
        return ($GLOBALS['cover_sync_http_transport'])($url, $headers, $timeout);
    }
    $http_response_header = [];
    $context = stream_context_create(['http' => [
        'method' => 'GET',
        'header' => implode("\r\n", $headers),
        'timeout' => $timeout,
        'ignore_errors' => true,
        'follow_location' => 0,
        'max_redirects' => 0,
    ]]);
    $body = @file_get_contents($url, false, $context);
    $status = 0;
    $responseHeaders = [];
    foreach ($http_response_header ?? [] as $line) {
        if (preg_match('#^HTTP/\S+\s+(\d+)#', $line, $m)) {
            $status = (int) $m[1];
        } elseif (str_contains($line, ':')) {
            [$name, $value] = explode(':', $line, 2);
            $responseHeaders[strtolower(trim($name))] = trim($value);
        }
    }
    return ['status' => $status, 'headers' => $responseHeaders, 'body' => $body === false ? '' : $body, 'error' => $body === false ? (error_get_last()['message'] ?? 'request failed') : null, 'final_url' => $url];
}

function http_request(string $url, array $headers, int $timeout = 30, int $maxRetries = 3): array
{
    $attempt = 0;
    while (true) {
        $attempt++;
        $response = http_request_once($url, $headers, $timeout);
        $status = (int) ($response['status'] ?? 0);
        if (!in_array($status, [429, 500, 502, 503, 504], true)) {
            return $response;
        }
        if ($attempt >= $maxRetries) {
            return $response;
        }
        $responseHeaders = $response['headers'] ?? [];
        $retryAfter = isset($responseHeaders['retry-after']) ? (int) $responseHeaders['retry-after'] : 0;
        $sleep = $retryAfter > 0 ? $retryAfter : min(30, 2 ** $attempt) + random_int(0, 1000) / 1000;
        cover_sync_sleep(min(30.0, (float) $sleep));
    }
}

function resolve_redirect_url(string $baseUrl, string $location): string
{
    if (preg_match('#^https?://#i', $location)) {
        return $location;
    }
    $scheme = parse_url($baseUrl, PHP_URL_SCHEME);
    $host = parse_url($baseUrl, PHP_URL_HOST);
    if (!is_string($scheme) || !is_string($host)) {
        throw new RuntimeException('cannot resolve redirect URL');
    }
    if (str_starts_with($location, '/')) {
        return $scheme . '://' . $host . $location;
    }
    $path = parse_url($baseUrl, PHP_URL_PATH);
    $dir = rtrim(str_replace('\\', '/', dirname(is_string($path) ? $path : '/')), '/');
    return $scheme . '://' . $host . ($dir === '' ? '/' : $dir . '/') . $location;
}

function http_request_follow_image_redirects(string $url, array $conditionalHeaders, int $timeout = 45, int $maxRedirects = 5): array
{
    $current = $url;
    for ($redirects = 0; $redirects <= $maxRedirects; $redirects++) {
        $scheme = strtolower((string) parse_url($current, PHP_URL_SCHEME));
        if (!in_array($scheme, ['http', 'https'], true)) {
            throw new RuntimeException('invalid image URL scheme');
        }
        $response = http_request_once($current, image_request_headers($conditionalHeaders), $timeout);
        $response['final_url'] = $current;
        $status = (int) ($response['status'] ?? 0);
        if (in_array($status, [301, 302, 303, 307, 308], true)) {
            $location = $response['headers']['location'] ?? null;
            if (!is_string($location) || trim($location) === '') {
                throw new RuntimeException('image redirect missing Location');
            }
            if ($redirects === $maxRedirects) {
                throw new RuntimeException('too many image redirects');
            }
            $current = resolve_redirect_url($current, $location);
            continue;
        }
        return $response;
    }
    throw new RuntimeException('too many image redirects');
}

function fetch_subject_page(int $offset): array
{
    if ($offset < 0) {
        throw new InvalidArgumentException('Bangumi API offset must be non-negative');
    }
    $url = BANGUMI_SUBJECTS_API . '?type=' . SUBJECT_TYPE_ANIME . '&limit=' . PAGE_LIMIT . '&offset=' . $offset;
    $response = http_request($url, api_request_headers($url));
    if ((int) ($response['status'] ?? 0) >= 300 && (int) ($response['status'] ?? 0) < 400) {
        throw new RuntimeException('Bangumi API redirect refused');
    }
    if (($response['status'] ?? 0) !== 200) {
        throw new RuntimeException('Bangumi API failed: HTTP ' . ($response['status'] ?? 0));
    }
    $json = json_decode((string) $response['body'], true);
    if (!is_array($json) || array_is_list($json)) {
        throw new RuntimeException('Bangumi API JSON parse failed or returned non-object');
    }
    foreach (['total', 'limit', 'offset'] as $key) {
        if (!isset($json[$key]) || !is_int($json[$key]) || $json[$key] < 0) {
            throw new RuntimeException('Bangumi API page field invalid: ' . $key);
        }
    }
    if ($json['limit'] < 1 || $json['limit'] > PAGE_LIMIT) {
        throw new RuntimeException('Bangumi API returned unsupported limit');
    }
    if ($json['offset'] !== $offset) {
        throw new RuntimeException('Bangumi API returned unexpected offset');
    }
    if (!isset($json['data']) || !is_array($json['data'])) {
        throw new RuntimeException('Bangumi API data field invalid');
    }
    if ($offset < $json['total'] && count($json['data']) === 0) {
        throw new RuntimeException('Bangumi API returned empty data before total was reached');
    }
    return $json;
}

function subject_large_image_url(array $item): ?string
{
    if (!isset($item['images']) || !is_array($item['images'])) {
        return null;
    }
    $url = $item['images']['large'] ?? null;
    if (!is_string($url) || trim($url) === '') {
        return null;
    }
    $path = parse_url($url, PHP_URL_PATH);
    if (is_string($path) && basename($path) === 'no_icon_subject.png') {
        return null;
    }
    return $url;
}

function image_type_from_bytes(string $data, string $contentType): ?array
{
    $lower = strtolower(strtok($contentType, ';') ?: '');
    if (str_starts_with($data, "\xFF\xD8\xFF") && in_array($lower, ['image/jpeg', 'image/jpg'], true)) return ['image/jpeg', 'jpg'];
    if (str_starts_with($data, "\x89PNG\r\n\x1A\n") && $lower === 'image/png') return ['image/png', 'png'];
    if (substr($data, 0, 4) === 'RIFF' && substr($data, 8, 4) === 'WEBP' && $lower === 'image/webp') return ['image/webp', 'webp'];
    return null;
}


function validate_jpeg_structure(string $data): bool
{
    return str_starts_with($data, "\xFF\xD8") && str_ends_with($data, "\xFF\xD9");
}

function validate_png_structure(string $data): bool
{
    if (!str_starts_with($data, "\x89PNG\r\n\x1A\n")) return false;
    $offset = 8;
    $len = strlen($data);
    while ($offset + 12 <= $len) {
        $length = unpack('N', substr($data, $offset, 4))[1];
        $type = substr($data, $offset + 4, 4);
        $chunkStart = $offset + 8;
        $crcStart = $chunkStart + $length;
        if ($length < 0 || $crcStart + 4 > $len) return false;
        $chunkData = substr($data, $chunkStart, $length);
        $expected = unpack('N', substr($data, $crcStart, 4))[1];
        $actual = crc32($type . $chunkData);
        if (($actual & 0xffffffff) !== $expected) return false;
        $offset = $crcStart + 4;
        if ($type === 'IEND') return $offset === $len;
    }
    return false;
}

function validate_webp_structure(string $data): bool
{
    if (strlen($data) < 12 || substr($data, 0, 4) !== 'RIFF' || substr($data, 8, 4) !== 'WEBP') return false;
    $declared = unpack('V', substr($data, 4, 4))[1] + 8;
    return $declared === strlen($data);
}

function validate_image_structure_bytes(string $data, string $extension): bool
{
    return match ($extension) {
        'jpg' => validate_jpeg_structure($data),
        'png' => validate_png_structure($data),
        'webp' => validate_webp_structure($data),
        default => false,
    };
}

function assert_image_decoder_available(): void
{
    if (!function_exists('imagecreatefromstring') && !class_exists('Imagick')) {
        throw new RuntimeException('no reliable image decoder available; enable GD or Imagick');
    }
}

function decode_image_fully(string $data): void
{
    assert_image_decoder_available();
    set_error_handler(static function (): bool { throw new RuntimeException('image decode warning'); });
    try {
        if (function_exists('imagecreatefromstring')) {
            $image = imagecreatefromstring($data);
            if ($image === false) throw new RuntimeException('image decode failed');
            return;
        }
        $image = new Imagick();
        $image->readImageBlob($data);
        $image->clear();
    } finally {
        restore_error_handler();
    }
}

function validate_image_file(string $path, string $contentType): array
{
    if (!is_file($path) || filesize($path) < 32 || filesize($path) > 20 * 1024 * 1024) {
        throw new RuntimeException('downloaded file size is invalid');
    }
    $data = file_get_contents($path);
    if ($data === false) {
        throw new RuntimeException('cannot read downloaded file');
    }
    $prefix = ltrim(substr($data, 0, 64));
    if (str_starts_with($prefix, '<') || str_starts_with($prefix, '{') || str_starts_with($prefix, '[')) {
        throw new RuntimeException('downloaded content is not an image');
    }
    $type = image_type_from_bytes($data, $contentType);
    if ($type === null) {
        throw new RuntimeException('unsupported or mismatched image type: ' . $contentType);
    }
    $finfo = new finfo(FILEINFO_MIME_TYPE);
    $detectedMime = $finfo->file($path);
    if ($detectedMime !== $type[0]) {
        throw new RuntimeException('finfo MIME does not match image type');
    }
    $imageSize = @getimagesize($path);
    if (!is_array($imageSize) || ($imageSize[0] ?? 0) <= 0 || ($imageSize[1] ?? 0) <= 0 || ($imageSize['mime'] ?? null) !== $type[0]) {
        throw new RuntimeException('downloaded image structure is invalid');
    }
    if (!validate_image_structure_bytes($data, $type[1])) {
        throw new RuntimeException('downloaded image container is incomplete');
    }
    decode_image_fully($data);
    return ['mime_type' => $type[0], 'extension' => $type[1], 'file_size' => filesize($path), 'sha256' => hash_file('sha256', $path)];
}

function download_image_to_tmp(int $subjectId, string $url, array $conditionalHeaders = []): array
{
    $baseTmp = tempnam(cover_sync_paths()['tmp'], $subjectId . '-');
    if ($baseTmp === false) {
        throw new RuntimeException('cannot create temp image file');
    }
    $tmp = $baseTmp . '.part';
    @unlink($baseTmp);
    try {
        $response = http_request_follow_image_redirects($url, $conditionalHeaders, 45);
        if (($response['status'] ?? 0) === 304) {
            if (is_file($tmp)) { @unlink($tmp); }
            return ['not_modified' => true, 'headers' => $response['headers'] ?? [], 'final_url' => $response['final_url'] ?? $url];
        }
    if (($response['status'] ?? 0) !== 200) {
        throw new RuntimeException('image download failed: HTTP ' . ($response['status'] ?? 0));
    }
    $finalUrl = $response['final_url'] ?? $url;
    $finalPath = parse_url($finalUrl, PHP_URL_PATH);
    if (is_string($finalPath) && basename($finalPath) === 'no_icon_subject.png') {
        throw new RemoteMissingCover('Bangumi no-icon placeholder rejected');
    }
    if (file_put_contents($tmp, (string) $response['body'], LOCK_EX) === false) {
        throw new RuntimeException('cannot write temp image');
    }
    $meta = validate_image_file($tmp, (string) (($response['headers']['content-type'] ?? '')));
    $meta['tmp_path'] = $tmp;
    $meta['etag'] = $response['headers']['etag'] ?? null;
    $meta['last_modified'] = $response['headers']['last-modified'] ?? null;
    $meta['final_url'] = $finalUrl;
    return $meta;
    } catch (Throwable $exc) {
        if (is_file($tmp)) { @unlink($tmp); }
        throw $exc;
    }
}

function upsert_observed(int $subjectId, ?string $url, string $mode): string
{
    $pdo = db();
    $existing = manifest_row($subjectId);
    $now = now_utc();
    $hasArtifact = $existing && !empty($existing['relative_path']) && local_cover_ok($existing['relative_path'] ?? null, $existing);
    if ($url === null || $url === '') {
        $status = $hasArtifact ? 'remote_missing' : 'no_cover';
        $artifact = $hasArtifact ? 'available' : 'missing';
        $result = 'remote_missing';
    } elseif (!$existing || !$hasArtifact) {
        $status = 'pending';
        $artifact = $hasArtifact ? 'available' : 'missing';
        $result = 'updated';
    } elseif (($existing['downloaded_url'] ?? null) === $url) {
        $status = in_array(($existing['deploy_status'] ?? ''), ['pending_deploy', 'mapping_failed'], true)
            ? (string) $existing['deploy_status']
            : 'unchanged';
        $artifact = 'available';
        $result = 'unchanged';
    } else {
        $status = 'pending_update';
        $artifact = 'available';
        $result = 'updated';
    }
    $deploySql = $existing ? '' : ", deploy_status = 'pending_deploy'";
    $stmt = $pdo->prepare("INSERT INTO cover_manifest (subject_id, subject_type, observed_url, status, last_seen_at, last_checked_at, artifact_status, deploy_status, last_check_result, checked_at)
        VALUES (:id, 2, :url, :status, :seen, :checked, :artifact, 'pending_deploy', :result, :checked)
        ON CONFLICT(subject_id) DO UPDATE SET observed_url = excluded.observed_url, status = excluded.status,
        last_seen_at = excluded.last_seen_at, last_checked_at = excluded.last_checked_at, checked_at = excluded.checked_at,
        artifact_status = :artifact, last_check_result = :result, last_error = NULL, error_message = NULL{$deploySql}");
    $stmt->execute(['id' => $subjectId, 'url' => $url, 'status' => $status, 'seen' => $now, 'checked' => $now, 'artifact' => $artifact, 'result' => $result]);
    return $status;
}

function manifest_row(int $subjectId): ?array
{
    $stmt = db()->prepare('SELECT * FROM cover_manifest WHERE subject_id = :id AND subject_type = 2');
    $stmt->execute(['id' => $subjectId]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    return $row ?: null;
}

function local_cover_ok(?string $relativePath, ?array $row = null): bool
{
    if (!$relativePath) return false;
    try {
        $path = cover_absolute_path($relativePath);
    } catch (InvalidArgumentException) {
        return false;
    }
    if (!is_file($path) || filesize($path) <= 0) return false;
    $data = file_get_contents($path);
    if (!is_string($data)) return false;
    $type = image_type_from_bytes($data, mime_content_type($path) ?: '');
    if ($type === null) return false;
    $extension = strtolower(pathinfo($relativePath, PATHINFO_EXTENSION));
    if ($extension === 'jpeg') $extension = 'jpg';
    if ($extension !== $type[1]) return false;
    $imageSize = @getimagesize($path);
    if (!is_array($imageSize) || ($imageSize[0] ?? 0) <= 0 || ($imageSize[1] ?? 0) <= 0) return false;
    if ($row !== null) {
        if (isset($row['file_size']) && $row['file_size'] !== null && (int) $row['file_size'] !== filesize($path)) return false;
        if (!empty($row['sha256']) && hash_file('sha256', $path) !== $row['sha256']) return false;
    }
    return true;
}

function mark_failed(int $subjectId, string $message): void
{
    $stmt = db()->prepare("UPDATE cover_manifest
        SET status = 'failed', retry_count = retry_count + 1, error_message = :error,
            last_check_result = 'http_failed', last_error = :error, last_checked_at = :checked, checked_at = :checked
        WHERE subject_id = :id");
    $stmt->execute(['id' => $subjectId, 'error' => mb_substr($message, 0, 1000), 'checked' => now_utc()]);
}


function move_no_clobber(string $source, string $target): void
{
    $in = fopen($source, 'rb');
    if ($in === false) {
        throw new RuntimeException('cannot open temp cover for read');
    }
    $out = fopen($target, 'xb');
    if ($out === false) {
        fclose($in);
        throw new RuntimeException('target cover already exists');
    }
    try {
        if (stream_copy_to_stream($in, $out) === false) {
            throw new RuntimeException('cannot write target cover');
        }
    } finally {
        fclose($in);
        fclose($out);
    }
    if (!unlink($source)) {
        throw new RuntimeException('cannot remove temp cover after move');
    }
}

function versioned_cover_filename(string $remoteFilename, string $sha256, int $length = 12): string
{
    $extension = pathinfo($remoteFilename, PATHINFO_EXTENSION);
    $stem = substr($remoteFilename, 0, -strlen('.' . $extension));
    return $stem . '--' . substr($sha256, 0, $length) . '.' . $extension;
}

function store_verified_tmp_cover(int $subjectId, string $sourceUrl, array $meta): array
{
    $remoteFilename = safe_remote_filename($subjectId, $sourceUrl, $meta['extension']);
    $relative = cover_relative_path($subjectId, $remoteFilename);
    $target = cover_absolute_path($relative);
    $tmp = (string) $meta['tmp_path'];
    if (is_file($target)) {
        $existingSha = hash_file('sha256', $target);
        if ($existingSha === $meta['sha256']) {
            return ['remote_filename' => $remoteFilename, 'relative_path' => $relative, 'stored' => false];
        }
        foreach ([12, 64] as $length) {
            $localFilename = versioned_cover_filename($remoteFilename, $meta['sha256'], $length);
            $relative = cover_relative_path($subjectId, $localFilename);
            $target = cover_absolute_path($relative);
            if (!is_file($target)) {
                break;
            }
            if (hash_file('sha256', $target) === $meta['sha256']) {
                return ['remote_filename' => $remoteFilename, 'relative_path' => $relative, 'stored' => false];
            }
            if ($length === 64) {
                throw new RuntimeException('versioned cover SHA collision for subject_id=' . $subjectId);
            }
        }
    }
    $targetDir = dirname($target);
    if (!is_dir($targetDir) && !mkdir($targetDir, 0775, true) && !is_dir($targetDir)) {
        throw new RuntimeException('cannot create cover directory');
    }
    move_no_clobber($tmp, $target);
    return ['remote_filename' => $remoteFilename, 'relative_path' => $relative, 'stored' => true];
}

function apply_one(int $subjectId, bool $dryRun = false): bool
{
    $row = manifest_row($subjectId);
    if (!$row || !($row['observed_url'] ?? null)) return false;
    if ($dryRun) {
        echo "dry-run download subject_id={$subjectId} url={$row['observed_url']}\n";
        return true;
    }
    $ownedTmp = null;
    db()->prepare("UPDATE cover_manifest SET status = 'downloading', last_check_result = 'downloading', checked_at = :checked WHERE subject_id = :id")
        ->execute(['checked' => now_utc(), 'id' => $subjectId]);
    try {
        $meta = download_image_to_tmp($subjectId, $row['observed_url']);
        $ownedTmp = $meta['tmp_path'] ?? null;
        if (!is_string($ownedTmp) || $ownedTmp === '' || !is_file($ownedTmp)) {
            throw new RuntimeException('download did not return an owned temp file');
        }
        $stored = store_verified_tmp_cover($subjectId, (string) $row['observed_url'], $meta);
        if (!is_file($ownedTmp)) {
            $ownedTmp = null;
        }
        $remoteFilename = $stored['remote_filename'];
        $relative = $stored['relative_path'];
        $stmt = db()->prepare('UPDATE cover_manifest SET downloaded_url = observed_url, remote_filename = :remote_filename, relative_path = :path, mime_type = :mime,
            file_extension = :ext, file_size = :size, sha256 = :sha, etag = :etag, last_modified = :lm,
            last_downloaded_at = :downloaded, last_checked_at = :checked, checked_at = :checked, status = :status, artifact_status = \'available\', deploy_status = :deploy_status, last_check_result = \'updated\', last_success_at = :downloaded, error_message = NULL, last_error = NULL WHERE subject_id = :id');
        $stmt->execute(['status' => ((bool) $GLOBALS['cover_sync_options']['write-mysql'] ? 'downloaded' : 'pending_deploy'), 'deploy_status' => ((bool) $GLOBALS['cover_sync_options']['write-mysql'] ? 'deployed' : 'pending_deploy'), 'remote_filename' => $remoteFilename, 'path' => $relative, 'mime' => $meta['mime_type'], 'ext' => $meta['extension'], 'size' => $meta['file_size'], 'sha' => $meta['sha256'], 'etag' => $meta['etag'], 'lm' => $meta['last_modified'], 'downloaded' => now_utc(), 'checked' => now_utc(), 'id' => $subjectId]);
        if ((bool) $GLOBALS['cover_sync_options']['write-mysql']) {
            try {
                sync_mysql_cover_cache($subjectId, 'cached', $remoteFilename, (string) $row['observed_url'], $relative, null, $meta);
                db()->prepare("UPDATE cover_manifest SET status = 'downloaded', deploy_status = 'deployed', last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                    ->execute(['checked' => now_utc(), 'id' => $subjectId]);
            } catch (Throwable $mappingError) {
                db()->prepare("UPDATE cover_manifest SET status = 'mapping_failed', deploy_status = 'mapping_failed', error_message = :error, last_error = :error, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                    ->execute(['error' => mb_substr('cover_cache mapping failed: ' . $mappingError->getMessage(), 0, 1000), 'checked' => now_utc(), 'id' => $subjectId]);
                return false;
            }
        }
        // Keep previous cover files until an explicit cleanup-covers --apply run.
        return true;
    } catch (RemoteMissingCover $exc) {
        $hasArtifact = !empty($row['relative_path']);
        $status = $hasArtifact ? 'remote_missing' : 'no_cover';
        $artifact = $hasArtifact ? 'available' : 'missing';
        db()->prepare('UPDATE cover_manifest SET status = :status, artifact_status = :artifact, last_check_result = :result, last_error = :error, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id')
            ->execute(['status' => $status, 'artifact' => $artifact, 'result' => 'remote_missing', 'error' => mb_substr($exc->getMessage(), 0, 1000), 'checked' => now_utc(), 'id' => $subjectId]);
        return false;
    } catch (Throwable $exc) {
        mark_failed($subjectId, $exc->getMessage());
        // cover_cache represents the website's last safe display mapping; never write
        // transient download failures to MariaDB or disable a previous cached cover.
        return false;
    } finally {
        if (is_string($ownedTmp) && is_file($ownedTmp)) {
            if (!@unlink($ownedTmp)) {
                error_log('ChronoShelter cover sync could not remove temp file: ' . $ownedTmp);
            }
        }
    }
}

function sync_mysql_cover_cache(int $subjectId, string $status, ?string $remoteFilename, ?string $sourceUrl, ?string $relativePath, ?string $error, array $meta): void
{
    $pdo = db_library();
    $stmt = $pdo->prepare('INSERT INTO cover_cache (subject_id, status, remote_filename, source_url, local_path, error, content_type, file_size, sha256)
        VALUES (:id, :status, :remote_filename, :source_url, :path, :error, :content_type, :file_size, :sha256)
        ON DUPLICATE KEY UPDATE status = VALUES(status), remote_filename = VALUES(remote_filename), source_url = VALUES(source_url),
            local_path = VALUES(local_path), error = VALUES(error), content_type = VALUES(content_type), file_size = VALUES(file_size),
            sha256 = VALUES(sha256), updated_at = CURRENT_TIMESTAMP');
    $stmt->execute([
        'id' => $subjectId,
        'status' => $status,
        'remote_filename' => $remoteFilename,
        'source_url' => $sourceUrl,
        'path' => $relativePath,
        'error' => $error,
        'content_type' => $meta['mime_type'] ?? null,
        'file_size' => $meta['file_size'] ?? null,
        'sha256' => $meta['sha256'] ?? null,
    ]);
}

function current_run(string $type, bool $resume): array
{
    $pdo = db();
    if ($resume) {
        $stmt = $pdo->prepare('SELECT * FROM sync_runs WHERE run_type = :type AND run_status = \'running\' ORDER BY started_at DESC LIMIT 1');
        $stmt->execute(['type' => $type]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if ($row) return $row;
    }
    $run = ['run_id' => $type . '-' . gmdate('YmdHis'), 'run_type' => $type, 'next_offset' => 0, 'total' => null, 'started_at' => now_utc(), 'updated_at' => now_utc(), 'completed_at' => null, 'run_status' => 'running'];
    $stmt = $pdo->prepare('INSERT INTO sync_runs (run_id, run_type, next_offset, total, started_at, updated_at, run_status) VALUES (:run_id, :run_type, :next_offset, :total, :started_at, :updated_at, :run_status)');
    $stmt->execute([
        'run_id' => $run['run_id'],
        'run_type' => $run['run_type'],
        'next_offset' => $run['next_offset'],
        'total' => $run['total'],
        'started_at' => $run['started_at'],
        'updated_at' => $run['updated_at'],
        'run_status' => $run['run_status'],
    ]);
    return $run;
}

function update_run(string $runId, int $nextOffset, ?int $total, string $status = 'running'): void
{
    db()->prepare('UPDATE sync_runs SET next_offset = :offset, total = :total, updated_at = :updated, completed_at = :completed, run_status = :status WHERE run_id = :id')
        ->execute(['offset' => $nextOffset, 'total' => $total, 'updated' => now_utc(), 'completed' => $status === 'completed' ? now_utc() : null, 'status' => $status, 'id' => $runId]);
}

function stats_template(string $type): array
{
    return ['task_type' => $type, 'api_pages' => 0, 'scanned_anime' => 0, 'with_cover' => 0, 'without_cover' => 0, 'new_downloads' => 0, 'existing_skipped' => 0, 'new_anime' => 0, 'url_changes' => 0, 'deep_changes' => 0, 'remote_missing' => 0, 'update_success' => 0, 'update_failed' => 0, 'download_bytes' => 0, 'manifest_records' => 0, 'complete' => false, 'next_offset' => 0, 'elapsed_seconds' => 0.0];
}

function scan_pages(string $mode, array $options): array
{
    $start = microtime(true);
    $stats = stats_template($mode);
    $run = current_run($mode, (bool) $options['resume']);
    $offset = (int) $run['next_offset'];
    $total = $run['total'] !== null ? (int) $run['total'] : null;
    $processedItems = 0;
    $changes = [];
    while ($total === null || $offset < $total) {
        if ($options['max-pages'] !== null && $stats['api_pages'] >= (int) $options['max-pages']) break;
        $page = fetch_subject_page($offset);
        $total = (int) ($page['total'] ?? 0);
        $items = $page['data'] ?? [];
        $pageConsumed = 0;
        foreach ($items as $item) {
            if ($options['max-items'] !== null && $processedItems >= (int) $options['max-items']) {
                update_run($run['run_id'], $offset, $total, 'running');
                break 2;
            }
            $offset++;
            $pageConsumed++;
            $id = (int) ($item['id'] ?? 0);
            if ($id <= 0) { throw new RuntimeException('Bangumi API subject id invalid'); }
            if ((int) ($item['type'] ?? 0) !== SUBJECT_TYPE_ANIME) continue;
            $url = subject_large_image_url($item);
            $before = manifest_row($id);
            $status = upsert_observed($id, is_string($url) && $url !== '' ? $url : null, $mode);
            $stats['scanned_anime']++;
            $processedItems++;
            $url ? $stats['with_cover']++ : $stats['without_cover']++;
            if (!$before) $stats['new_anime']++;
            if ($status === 'pending_update') $stats['url_changes']++;
            if ($status === 'remote_missing') $stats['remote_missing']++;
            if ($status === 'unchanged' || $status === 'downloaded') $stats['existing_skipped']++;
            if ($mode === 'sync' && in_array($status, ['pending', 'pending_update'], true)) {
                if (apply_one($id, (bool) $options['dry-run'])) $stats['new_downloads']++;
                else $stats['update_failed']++;
                cover_sync_sleep((float) $options['download-delay']);
            }
            if (in_array($status, ['pending', 'pending_update', 'remote_missing'], true)) {
                $after = manifest_row($id);
                $changes[] = ['subject_id' => $id, 'status' => $status, 'downloaded_url' => $before['downloaded_url'] ?? null, 'observed_url' => $after['observed_url'] ?? null];
            }
        }
        if ($pageConsumed === 0 && $offset < (int) $total) {
            throw new RuntimeException('Bangumi API page made no cursor progress');
        }
        $stats['api_pages']++;
        update_run($run['run_id'], $offset, $total, 'running');
        cover_sync_sleep((float) $options['api-delay']);
    }
    $complete = $total !== null && $offset >= $total && ($options['max-pages'] === null) && ($options['max-items'] === null);
    update_run($run['run_id'], $offset, $total, $complete ? 'completed' : 'running');
    if ($mode === 'check-updates') write_report($stats, $changes);
    $stats['complete'] = $complete;
    $stats['next_offset'] = $offset;
    $stats['manifest_records'] = (int) db()->query('SELECT COUNT(*) FROM cover_manifest')->fetchColumn();
    $stats['elapsed_seconds'] = round(microtime(true) - $start, 3);
    return $stats;
}

function write_report(array $stats, array $changes): void
{
    $date = gmdate('Y-m-d');
    $base = cover_sync_paths()['reports'] . '/cover-changes-' . $date;
    $report = ['summary' => $stats, 'changes' => $changes];
    file_put_contents($base . '.json', json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
    $txt = "ChronoShelter cover changes {$date}\n";
    foreach ($stats as $key => $value) $txt .= "{$key}: {$value}\n";
    foreach ($changes as $change) $txt .= json_encode($change, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
    file_put_contents($base . '.txt', $txt);
}

function apply_updates(array $options): array
{
    $stats = stats_template('apply-updates');
    $sql = "SELECT subject_id FROM cover_manifest WHERE subject_type = 2 AND status IN ('pending','pending_update') AND observed_url IS NOT NULL ORDER BY subject_id";
    if ($options['subject-id']) $sql = 'SELECT subject_id FROM cover_manifest WHERE subject_id = ' . (int) $options['subject-id'] . " AND subject_type = 2";
    $rows = db()->query($sql)->fetchAll(PDO::FETCH_COLUMN);
    $limit = $options['max-items'] !== null ? (int) $options['max-items'] : count($rows);
    foreach (array_slice($rows, 0, $limit) as $id) {
        if (apply_one((int) $id, (bool) $options['dry-run'])) $stats['update_success']++; else $stats['update_failed']++;
        cover_sync_sleep((float) $options['download-delay']);
    }
    $stats['complete'] = count($rows) <= $limit;
    $stats['manifest_records'] = (int) db()->query('SELECT COUNT(*) FROM cover_manifest')->fetchColumn();
    return $stats;
}

function retry_failed(array $options): array
{
    db()->exec("UPDATE cover_manifest SET status = CASE WHEN downloaded_url IS NULL THEN 'pending' ELSE 'pending_update' END WHERE subject_type = 2 AND status IN ('failed','mapping_failed')");
    return apply_updates($options);
}


function strict_manifest_cover_ok(array $row, ?string &$error = null): bool
{
    $relativePath = $row['relative_path'] ?? null;
    if (!is_string($relativePath) || $relativePath === '') { $error = 'missing relative_path'; return false; }
    try { $path = cover_absolute_path($relativePath); } catch (Throwable $exc) { $error = $exc->getMessage(); return false; }
    $root = realpath(cover_sync_paths()['covers']);
    $real = realpath($path);
    if ($root === false || $real === false || !str_starts_with($real, rtrim($root, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR)) { $error = 'cover path outside covers'; return false; }
    if (!is_file($path)) { $error = 'cover file missing'; return false; }
    if (!isset($row['file_size']) || (int) $row['file_size'] !== filesize($path)) { $error = 'file size mismatch'; return false; }
    if (empty($row['sha256']) || !preg_match('/^[a-f0-9]{64}$/i', (string) $row['sha256']) || hash_file('sha256', $path) !== strtolower((string) $row['sha256'])) { $error = 'sha256 mismatch'; return false; }
    if (empty($row['mime_type'])) { $error = 'missing mime_type'; return false; }
    try { $meta = validate_image_file($path, (string) $row['mime_type']); } catch (Throwable $exc) { $error = $exc->getMessage(); return false; }
    $ext = strtolower(pathinfo($relativePath, PATHINFO_EXTENSION));
    if ($ext === 'jpeg') $ext = 'jpg';
    if (!empty($row['file_extension']) && strtolower((string) $row['file_extension']) !== $meta['extension']) { $error = 'file extension mismatch'; return false; }
    if ($ext !== $meta['extension']) { $error = 'path extension mismatch'; return false; }
    return true;
}

function verify_files(array $options): array
{
    $stats = stats_template('verify-files');
    $hadFailure = false;
    $rows = db()->query("SELECT subject_id, relative_path, mime_type, file_extension, file_size, sha256 FROM cover_manifest WHERE subject_type = 2 AND relative_path IS NOT NULL")->fetchAll(PDO::FETCH_ASSOC);
    foreach ($rows as $row) {
        $stats['scanned_anime']++;
        $error = null;
        if (!strict_manifest_cover_ok($row, $error)) {
            $hadFailure = true;
            db()->prepare("UPDATE cover_manifest
                SET artifact_status = 'invalid', last_check_result = 'local_invalid',
                    last_error = :error, error_message = :error, last_checked_at = :checked, checked_at = :checked
                WHERE subject_id = :id")
                ->execute(['error' => 'local file invalid: ' . $error, 'checked' => now_utc(), 'id' => $row['subject_id']]);
            $stats['url_changes']++;
        } else {
            $stats['existing_skipped']++;
        }
    }
    if ($hadFailure) {
        $stats['update_failed']++;
    }
    $stats['complete'] = !$hadFailure;
    $stats['manifest_records'] = (int) db()->query('SELECT COUNT(*) FROM cover_manifest')->fetchColumn();
    return $stats;
}

function deep_check(array $options): array
{
    $stats = stats_template('deep-check');
    if ($options['all'] && !$options['confirm-all']) {
        fwrite(STDERR, "Refusing --all without --confirm-all\n");
        exit(2);
    }
    if ($options['subject-id']) {
        $rows = [manifest_row((int) $options['subject-id'])];
    } elseif ($options['all']) {
        $rows = db()->query("SELECT * FROM cover_manifest WHERE subject_type = 2 AND downloaded_url IS NOT NULL")->fetchAll(PDO::FETCH_ASSOC);
        echo 'deep-check --all count=' . count($rows) . "\n";
    } else {
        $sample = max(1, (int) ($options['sample'] ?? 100));
        $rows = db()->query("SELECT * FROM cover_manifest WHERE subject_type = 2 AND downloaded_url IS NOT NULL ORDER BY RANDOM() LIMIT {$sample}")->fetchAll(PDO::FETCH_ASSOC);
    }
    foreach (array_filter($rows) as $row) {
        $stats['scanned_anime']++;
        $ownedTmp = null;
        $headers = [];
        if ($row['etag']) $headers[] = 'If-None-Match: ' . $row['etag'];
        if ($row['last_modified']) $headers[] = 'If-Modified-Since: ' . $row['last_modified'];
        if ($options['dry-run']) continue;
        try {
            $meta = download_image_to_tmp((int) $row['subject_id'], (string) $row['downloaded_url'], $headers);
            if (($meta['not_modified'] ?? false) === true) {
                db()->prepare("UPDATE cover_manifest SET last_check_result = 'unchanged', last_error = NULL, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                    ->execute(['checked' => now_utc(), 'id' => $row['subject_id']]);
                $stats['existing_skipped']++;
                continue;
            }
            $ownedTmp = $meta['tmp_path'] ?? null;
            if (!is_string($ownedTmp) || $ownedTmp === '' || !is_file($ownedTmp)) {
                throw new RuntimeException('deep-check did not return an owned temp file');
            }
            if (($meta['sha256'] ?? '') !== ($row['sha256'] ?? '')) {
                $stored = store_verified_tmp_cover((int) $row['subject_id'], (string) $row['downloaded_url'], $meta);
                if (!is_file($ownedTmp)) {
                    $ownedTmp = null;
                }
                db()->prepare("UPDATE cover_manifest SET remote_filename = :remote_filename, relative_path = :path, mime_type = :mime,
                    file_extension = :ext, file_size = :size, sha256 = :sha, etag = :etag, last_modified = :lm,
                    last_downloaded_at = :downloaded, last_checked_at = :checked, checked_at = :checked,
                    artifact_status = 'available', deploy_status = CASE WHEN deploy_status = 'mapping_failed' THEN 'mapping_failed' ELSE 'pending_deploy' END,
                    status = CASE WHEN deploy_status = 'mapping_failed' THEN 'mapping_failed' ELSE 'pending_deploy' END,
                    last_check_result = 'updated', last_success_at = :downloaded, error_message = NULL, last_error = NULL
                    WHERE subject_id = :id")
                    ->execute(['remote_filename' => $stored['remote_filename'], 'path' => $stored['relative_path'], 'mime' => $meta['mime_type'], 'ext' => $meta['extension'], 'size' => $meta['file_size'], 'sha' => $meta['sha256'], 'etag' => $meta['etag'], 'lm' => $meta['last_modified'], 'downloaded' => now_utc(), 'checked' => now_utc(), 'id' => $row['subject_id']]);
                $stats['deep_changes']++;
            } else {
                db()->prepare("UPDATE cover_manifest SET last_check_result = 'unchanged', last_error = NULL, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                    ->execute(['checked' => now_utc(), 'id' => $row['subject_id']]);
                $stats['existing_skipped']++;
            }
        } catch (RemoteMissingCover $exc) {
            db()->prepare("UPDATE cover_manifest SET last_check_result = 'remote_missing', last_error = :error, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                ->execute(['error' => mb_substr($exc->getMessage(), 0, 1000), 'checked' => now_utc(), 'id' => $row['subject_id']]);
            $stats['remote_missing']++;
        } catch (Throwable $exc) {
            db()->prepare("UPDATE cover_manifest SET last_check_result = 'http_failed', last_error = :error, error_message = :error, last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                ->execute(['error' => mb_substr($exc->getMessage(), 0, 1000), 'checked' => now_utc(), 'id' => $row['subject_id']]);
            $stats['update_failed']++;
        } finally {
            if (is_string($ownedTmp) && is_file($ownedTmp)) {
                if (!@unlink($ownedTmp)) {
                    error_log('ChronoShelter cover sync could not remove temp file: ' . $ownedTmp);
                }
            }
        }
        cover_sync_sleep((float) $options['download-delay']);
    }
    $stats['complete'] = true;
    $stats['manifest_records'] = (int) db()->query('SELECT COUNT(*) FROM cover_manifest')->fetchColumn();
    return $stats;
}

function export_mapping(array $options): array
{
    $stats = stats_template('export-mapping');
    $file = $options['file'] ?: (cover_sync_paths()['reports'] . '/cover-mapping-' . gmdate('Y-m-d-His') . '.jsonl');
    $dir = dirname((string) $file);
    if (!is_dir($dir) && !mkdir($dir, 0775, true) && !is_dir($dir)) {
        throw new RuntimeException('cannot create export directory');
    }
    $rows = db()->query("SELECT subject_id, status, artifact_status, deploy_status, last_check_result, remote_filename, downloaded_url AS source_url, relative_path AS local_path, mime_type AS content_type, file_size, sha256, COALESCE(last_downloaded_at, last_checked_at) AS updated_at FROM cover_manifest WHERE subject_type = 2 ORDER BY subject_id")->fetchAll(PDO::FETCH_ASSOC);
    $handle = fopen((string) $file, 'wb');
    if ($handle === false) {
        throw new RuntimeException('cannot open export file');
    }
    foreach ($rows as $row) {
        $export = null;
        if (!empty($row['local_path']) && local_cover_ok($row['local_path'], $row)) {
            $export = $row;
            $export['status'] = 'cached';
        } elseif (($row['artifact_status'] ?? '') === 'missing' && empty($row['source_url']) && empty($row['local_path']) && (($row['last_check_result'] ?? '') === 'remote_missing' || ($row['status'] ?? '') === 'no_cover')) {
            $export = [
                'subject_id' => (int) $row['subject_id'],
                'status' => 'no_cover',
                'remote_filename' => null,
                'source_url' => null,
                'local_path' => null,
                'content_type' => null,
                'file_size' => null,
                'sha256' => null,
                'updated_at' => $row['updated_at'] ?? now_utc(),
            ];
        }
        if ($export === null) {
            continue;
        }
        fwrite($handle, json_encode($export, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n");
        $stats['scanned_anime']++;
    }
    fclose($handle);
    echo "mapping_export_file: {$file}\n";
    $stats['complete'] = true;
    $stats['manifest_records'] = (int) db()->query('SELECT COUNT(*) FROM cover_manifest')->fetchColumn();
    return $stats;
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
    if ($relativePath === '') {
        throw new RuntimeException('cached mapping missing local_path for subject_id=' . $subjectId);
    }
    $absolute = cover_absolute_path($relativePath);
    $root = realpath(cover_sync_paths()['covers']);
    $real = realpath($absolute);
    if ($root === false || $real === false || !str_starts_with($real, rtrim($root, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR)) {
        throw new RuntimeException('mapped file is outside covers for subject_id=' . $subjectId);
    }
    $prefix = cover_partition_prefix($subjectId);
    $base = basename($relativePath);
    if (!str_starts_with($relativePath, $prefix) || !preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$/i', $base)) {
        throw new RuntimeException('mapped path does not match subject shard/name for subject_id=' . $subjectId);
    }
    if (!is_file($absolute)) {
        throw new RuntimeException('mapped file missing for subject_id=' . $subjectId);
    }
    if (!isset($row['file_size']) || $row['file_size'] === null || filesize($absolute) !== (int) $row['file_size']) {
        throw new RuntimeException('mapped file size mismatch for subject_id=' . $subjectId);
    }
    if (empty($row['sha256']) || !preg_match('/^[a-f0-9]{64}$/i', (string) $row['sha256']) || hash_file('sha256', $absolute) !== $row['sha256']) {
        throw new RuntimeException('mapped file sha256 mismatch for subject_id=' . $subjectId);
    }
    if (empty($row['content_type'])) {
        throw new RuntimeException('cached mapping missing content_type for subject_id=' . $subjectId);
    }
    $validated = validate_image_file($absolute, (string) $row['content_type']);
    if ($validated['sha256'] !== strtolower((string) $row['sha256']) || $validated['file_size'] !== (int) $row['file_size']) {
        throw new RuntimeException('mapped file metadata mismatch for subject_id=' . $subjectId);
    }
    $remoteFilename = (string) ($row['remote_filename'] ?? '');
    if ($remoteFilename === '' || !preg_match('/^' . preg_quote((string) $subjectId, '/') . '_[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$/i', $remoteFilename)) {
        throw new RuntimeException('unsafe remote_filename for subject_id=' . $subjectId);
    }
    if (str_contains($base, '--')) {
        $expectedStem = pathinfo($remoteFilename, PATHINFO_FILENAME);
        $expectedExt = strtolower(pathinfo($remoteFilename, PATHINFO_EXTENSION));
        if ($expectedExt === 'jpeg') $expectedExt = 'jpg';
        $sha = strtolower((string) $row['sha256']);
        $shortName = $expectedStem . '--' . substr($sha, 0, 12) . '.' . $expectedExt;
        $fullName = $expectedStem . '--' . $sha . '.' . $expectedExt;
        if ($base !== $shortName && $base !== $fullName) {
            throw new RuntimeException('versioned local_path does not match remote_filename and sha256 for subject_id=' . $subjectId);
        }
    }
    return [
        'subject_id' => $subjectId,
        'status' => 'cached',
        'remote_filename' => $remoteFilename,
        'source_url' => $row['source_url'] ?? null,
        'local_path' => $relativePath,
        'content_type' => $validated['mime_type'],
        'file_size' => filesize($absolute),
        'sha256' => strtolower((string) $row['sha256']),
        'updated_at' => $row['updated_at'] ?? null,
    ];
}

function import_mapping(array $options): array
{
    $stats = stats_template('import-mapping');
    $file = $options['file'];
    if (!$file || !is_file((string) $file)) {
        throw new RuntimeException('--file is required for import-mapping');
    }
    $rows = [];
    $seen = [];
    $handle = fopen((string) $file, 'rb');
    if ($handle === false) {
        throw new RuntimeException('cannot open mapping file');
    }
    while (($line = fgets($handle)) !== false) {
        $line = trim($line);
        if ($line === '') continue;
        $decoded = json_decode($line, true);
        if (!is_array($decoded)) {
            fclose($handle);
            throw new RuntimeException('invalid mapping JSON line');
        }
        $row = import_mapping_row_is_safe($decoded);
        if (isset($seen[$row['subject_id']])) {
            fclose($handle);
            throw new RuntimeException('duplicate subject_id in mapping: ' . $row['subject_id']);
        }
        $seen[$row['subject_id']] = true;
        $rows[] = $row;
    }
    fclose($handle);

    $pdo = db_library();
    $pdo->beginTransaction();
    try {
        $stmt = $pdo->prepare('INSERT INTO cover_cache (subject_id, status, remote_filename, source_url, local_path, content_type, file_size, sha256, updated_at)
            VALUES (:subject_id, :status, :remote_filename, :source_url, :local_path, :content_type, :file_size, :sha256, COALESCE(:updated_at, CURRENT_TIMESTAMP))
            ON DUPLICATE KEY UPDATE status = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', status, VALUES(status)),
                remote_filename = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', remote_filename, VALUES(remote_filename)),
                source_url = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', source_url, VALUES(source_url)),
                local_path = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', local_path, VALUES(local_path)),
                content_type = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', content_type, VALUES(content_type)),
                file_size = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', file_size, VALUES(file_size)),
                sha256 = IF(VALUES(status) = \'no_cover\' AND status = \'cached\', sha256, VALUES(sha256)), updated_at = VALUES(updated_at)');
        foreach ($rows as $row) {
            $stmt->execute($row);
            if ($row['status'] === 'cached') {
                db()->prepare("UPDATE cover_manifest SET deploy_status = 'deployed', status = 'downloaded', last_check_result = COALESCE(last_check_result, 'unchanged'), last_checked_at = :checked, checked_at = :checked WHERE subject_id = :id")
                    ->execute(['checked' => now_utc(), 'id' => $row['subject_id']]);
            }
            $stats['update_success']++;
        }
        $pdo->commit();
    } catch (Throwable $exc) {
        $pdo->rollBack();
        throw $exc;
    }
    $stats['complete'] = true;
    return $stats;
}

function cleanup_covers(array $options): array
{
    if ((bool) $options['apply']) {
        fwrite(STDERR, "cleanup-covers --apply is disabled until production cover_cache references or a trusted active mapping snapshot can be verified.\n");
        exit(2);
    }
    $stats = stats_template('cleanup-covers');
    $root = cover_sync_paths()['covers'];
    $subjects = $root . '/subjects';
    $referenced = [];
    foreach (db()->query("SELECT relative_path FROM cover_manifest WHERE subject_type = 2 AND relative_path IS NOT NULL") as $row) {
        $referenced[(string) $row['relative_path']] = true;
    }
    if (!is_dir($subjects)) {
        $stats['complete'] = true;
        return $stats;
    }
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($subjects, FilesystemIterator::SKIP_DOTS));
    foreach ($iterator as $fileInfo) {
        if (!$fileInfo->isFile()) continue;
        $path = $fileInfo->getPathname();
        $relative = str_replace('\\', '/', substr($path, strlen(rtrim($root, DIRECTORY_SEPARATOR)) + 1));
        if (isset($referenced[$relative])) continue;
        if (!preg_match('#^subjects/[0-9]{3,}/[0-9]{3}/[0-9]+_[A-Za-z0-9_-]+(?:--[a-f0-9]{12}|--[a-f0-9]{64})?\.(jpg|jpeg|png|webp)$#i', $relative)) continue;
        echo "cleanup_candidate: {$relative}\n";
        $stats['scanned_anime']++;
    }
    $stats['complete'] = true;
    return $stats;
}

function print_stats(array $stats): void
{
    foreach ($stats as $key => $value) {
        echo $key . ': ' . (is_bool($value) ? ($value ? 'yes' : 'no') : (string) $value) . "\n";
    }
}

function usage(): void
{
    echo "Usage: php bin/bangumi_covers.php <sync|check-updates|apply-updates|retry-failed|verify-files|deep-check|export-mapping|import-mapping|cleanup-covers> [options]\n";
    echo "All Bangumi subject scans are fixed to type=2, limit=50, images.large only.\n";
    echo "Default sync is offline: it writes SQLite, sets deploy_status=pending_deploy, then use export-mapping/import-mapping after copying covers.\n";
    echo "SQLite status is a deprecated compatibility summary; artifact_status, deploy_status and last_check_result carry the authoritative workflow state.\n";
}

function main(array $argv): int
{
    [$command, $options] = cli_options($argv);
    $GLOBALS['cover_sync_options'] = $options;
    try {
        ensure_runtime_dirs();
        $stats = match ($command) {
            'sync' => scan_pages('sync', $options),
            'check-updates' => scan_pages('check-updates', $options),
            'apply-updates' => apply_updates($options),
            'retry-failed' => retry_failed($options),
            'verify-files' => verify_files($options),
            'deep-check' => deep_check($options),
            'export-mapping' => export_mapping($options),
            'import-mapping' => import_mapping($options),
            'cleanup-covers' => cleanup_covers($options),
            default => null,
        };
        if ($stats === null) {
            usage();
            return 0;
        }
        print_stats($stats);
        return (($stats['update_failed'] ?? 0) > 0) ? 1 : 0;
    } catch (Throwable $exc) {
        fwrite(STDERR, 'ERROR: ' . $exc->getMessage() . "\n");
        return 1;
    }
}

if (realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) {
    exit(main($argv));
}
