<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

/**
 * Resolve a cover URL without performing any network I/O.
 *
 * Web requests must stay usable when Bangumi is unreachable. Cover downloads
 * are an offline maintenance task; a missing local file therefore resolves to
 * the bundled placeholder immediately.
 */
function cover_url(int $subjectId, ?string $localPath = null): string
{
    unset($localPath);
    $config = app_config()['covers'] ?? [];
    $directory = rtrim((string) ($config['directory'] ?? dirname(__DIR__) . '/covers'), "/\\");
    $publicPath = trim(str_replace('\\', '/', (string) ($config['public_path'] ?? 'covers')), '/');
    $placeholder = basename(str_replace('\\', '/', (string) ($config['placeholder'] ?? 'logo.png')));
    if ($placeholder === '' || $placeholder === '.' || $placeholder === '..') {
        $placeholder = 'logo.png';
    }

    $filename = $subjectId . '.jpg';
    $absolutePath = $directory . '/' . $filename;

    if (is_file($absolutePath) && filesize($absolutePath) > 0) {
        return h(($publicPath !== '' ? $publicPath . '/' : '') . $filename);
    }

    $placeholderPath = $directory . '/' . $placeholder;
    if (is_file($placeholderPath) && filesize($placeholderPath) > 0) {
        return h(($publicPath !== '' ? $publicPath . '/' : '') . rawurlencode($placeholder));
    }

    return 'static/img/placeholder.svg';
}
