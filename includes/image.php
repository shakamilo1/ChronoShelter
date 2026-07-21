<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

/**
 * Resolve a cover URL without performing any network I/O.
 *
 * Web requests must stay usable when Bangumi is unreachable. Cover downloads
 * are an offline CLI maintenance task; a missing, unsafe, or invalid local file
 * therefore resolves to the bundled fallback immediately.
 */
function cover_url(int $subjectId, ?string $localPath = null): string
{
    $config = app_config()['covers'] ?? [];
    $directory = rtrim((string) ($config['directory'] ?? dirname(__DIR__) . '/covers'), "/\\");
    $publicPath = trim(str_replace('\\', '/', (string) ($config['public_path'] ?? 'covers')), '/');
    $subjectsDirectory = trim((string) ($config['subjects_directory'] ?? 'subjects'), '/');
    $fallback = basename(str_replace('\\', '/', (string) ($config['fallback'] ?? ($config['placeholder'] ?? 'logo.png'))));
    if ($fallback === '' || $fallback === '.' || $fallback === '..') {
        $fallback = 'logo.png';
    }

    $relativePath = cover_existing_relative_path($directory, $subjectsDirectory, $subjectId, $localPath);
    if ($relativePath !== null) {
        return h(cover_public_url($publicPath, $relativePath));
    }

    $fallbackPath = $directory . '/' . $fallback;
    if (cover_file_is_valid($fallbackPath)) {
        return h(cover_public_url($publicPath, rawurlencode($fallback)));
    }

    return 'static/img/placeholder.svg';
}

function cover_existing_relative_path(string $directory, string $subjectsDirectory, int $subjectId, ?string $localPath): ?string
{
    $candidates = [];
    if ($localPath !== null && $localPath !== '') {
        $safe = cover_safe_relative_path($localPath);
        if ($safe !== null) {
            $candidates[] = $safe;
        }
    }
    foreach (['jpg', 'png', 'webp'] as $extension) {
        $candidates[] = cover_partition_relative_path($subjectId, $extension, $subjectsDirectory);
    }
    foreach (array_unique($candidates) as $relativePath) {
        if (cover_file_is_valid($directory . '/' . $relativePath)) {
            return $relativePath;
        }
    }
    return null;
}

function cover_partition_relative_path(int $subjectId, string $extension, string $subjectsDirectory = 'subjects'): string
{
    $subjectsDirectory = trim($subjectsDirectory, '/');
    $level1 = str_pad((string) intdiv($subjectId, 1000000), 3, '0', STR_PAD_LEFT);
    $level2 = str_pad((string) intdiv($subjectId % 1000000, 1000), 3, '0', STR_PAD_LEFT);
    return $subjectsDirectory . '/' . $level1 . '/' . $level2 . '/' . $subjectId . '.' . $extension;
}

function cover_safe_relative_path(string $path): ?string
{
    $path = trim(str_replace('\\', '/', $path), '/');
    if (str_starts_with($path, 'covers/')) {
        $path = substr($path, strlen('covers/'));
    }
    if (preg_match('#^subjects/[0-9]{3,}/[0-9]{3}/[0-9]+\.(jpg|png|webp)$#', $path)) {
        return $path;
    }
    if (preg_match('#^[0-9]+\.jpg$#', $path)) {
        return $path;
    }
    return null;
}

function cover_file_is_valid(string $path): bool
{
    if (!is_file($path) || filesize($path) <= 0) {
        return false;
    }
    $handle = fopen($path, 'rb');
    if ($handle === false) {
        return false;
    }
    $bytes = fread($handle, 16);
    fclose($handle);
    if ($bytes === false) {
        return false;
    }
    return str_starts_with($bytes, "\xFF\xD8\xFF")
        || str_starts_with($bytes, "\x89PNG\r\n\x1A\n")
        || (substr($bytes, 0, 4) === 'RIFF' && substr($bytes, 8, 4) === 'WEBP');
}

function cover_public_url(string $publicPath, string $relativePath): string
{
    $relativePath = implode('/', array_map('rawurlencode', explode('/', trim($relativePath, '/'))));
    return ($publicPath !== '' ? $publicPath . '/' : '') . $relativePath;
}
