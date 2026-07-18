<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function cover_url(int $subjectId, ?string $localPath = null): string
{
    if ($localPath) return h($localPath);
    $path = dirname(__DIR__) . '/covers/' . $subjectId . '.jpg';
    if (is_file($path)) return 'covers/' . $subjectId . '.jpg';
    return 'static/img/placeholder.svg';
}

function cache_cover(int $subjectId): bool
{
    $config = app_config()['covers'];
    $target = $config['directory'] . '/' . $subjectId . '.jpg';
    if (is_file($target) && filesize($target) > 0) return true;
    if (!is_dir($config['directory'])) mkdir($config['directory'], 0755, true);
    $url = sprintf($config['api_url'], $subjectId);
    $headers = @get_headers($url, true);
    $finalUrl = is_array($headers) && isset($headers['Location']) ? (is_array($headers['Location']) ? end($headers['Location']) : $headers['Location']) : $url;
    if ($finalUrl === $config['no_icon_url']) return false;
    $data = @file_get_contents($url);
    if ($data === false || strlen($data) < 1024) return false;
    $info = @getimagesizefromstring($data);
    if ($info === false || !in_array($info['mime'], ['image/jpeg', 'image/png', 'image/webp'], true)) return false;
    file_put_contents($target, $data);
    db_library()->prepare('INSERT INTO cover_cache (subject_id, status, local_path, content_type, file_size, width, height) VALUES (:id, \'cached\', :path, :type, :size, :width, :height) ON DUPLICATE KEY UPDATE status = \'cached\', local_path = VALUES(local_path), content_type = VALUES(content_type), file_size = VALUES(file_size), width = VALUES(width), height = VALUES(height)')
        ->execute(['id' => $subjectId, 'path' => 'covers/' . $subjectId . '.jpg', 'type' => $info['mime'], 'size' => strlen($data), 'width' => $info[0], 'height' => $info[1]]);
    return true;
}
