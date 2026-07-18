<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function cover_url(int $subjectId, ?string $localPath = null): string
{
    if ($localPath) return h($localPath);
    $path = dirname(__DIR__) . '/covers/' . $subjectId . '.jpg';
    if (is_file($path) && filesize($path) > 0) return 'covers/' . $subjectId . '.jpg';
    return cache_cover($subjectId) ? 'covers/' . $subjectId . '.jpg' : 'static/img/placeholder.svg';
}

function cache_cover(int $subjectId): bool
{
    $config = app_config()['covers'];
    $target = $config['directory'] . '/' . $subjectId . '.jpg';
    if (is_file($target) && filesize($target) > 0) return true;
    if (!is_dir($config['directory'])) mkdir($config['directory'], 0755, true);

    $url = sprintf($config['api_url'], $subjectId);
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'timeout' => 8,
            'follow_location' => 1,
            'max_redirects' => 3,
            'header' => "User-Agent: ChronoShelter/1.0\r\n",
        ],
    ]);
    $data = @file_get_contents($url, false, $context, 0, 5 * 1024 * 1024 + 1);
    $headers = $http_response_header ?? [];
    $finalUrl = image_final_location($headers) ?? $url;
    if ($finalUrl === $config['no_icon_url']) return false;
    if ($data === false || strlen($data) < 1024 || strlen($data) > 5 * 1024 * 1024) return false;
    $info = @getimagesizefromstring($data);
    if ($info === false || !in_array($info['mime'], ['image/jpeg', 'image/png', 'image/webp'], true)) return false;

    $tmp = $target . '.tmp.' . bin2hex(random_bytes(6));
    if (file_put_contents($tmp, $data, LOCK_EX) === false) return false;
    if (@getimagesize($tmp) === false) {
        @unlink($tmp);
        return false;
    }
    rename($tmp, $target);
    db_library()->prepare('INSERT INTO cover_cache (subject_id, status, local_path, content_type, file_size, width, height) VALUES (:id, \'cached\', :path, :type, :size, :width, :height) ON DUPLICATE KEY UPDATE status = \'cached\', local_path = VALUES(local_path), content_type = VALUES(content_type), file_size = VALUES(file_size), width = VALUES(width), height = VALUES(height)')
        ->execute(['id' => $subjectId, 'path' => 'covers/' . $subjectId . '.jpg', 'type' => $info['mime'], 'size' => strlen($data), 'width' => $info[0], 'height' => $info[1]]);
    return true;
}

function image_final_location(array $headers): ?string
{
    $location = null;
    foreach ($headers as $header) {
        if (is_string($header) && stripos($header, 'Location:') === 0) {
            $location = trim(substr($header, 9));
        }
    }
    return $location;
}
