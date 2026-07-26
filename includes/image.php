<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

/**
 * Generate a protected cover URL.
 *
 * Real covers keep their subject-specific URL. All missing covers share one
 * fixed URL so the browser downloads the placeholder only once per page.
 */
function cover_url(int $subjectId, ?string $localPath = null): string
{
    $config = app_config()['covers'] ?? [];

    $directory = rtrim(
        (string) ($config['directory'] ?? dirname(__DIR__) . '/covers'),
        "/\\"
    );

    $subjectsDirectory = trim(
        (string) ($config['subjects_directory'] ?? 'subjects'),
        '/'
    );

    $relativePath = cover_existing_relative_path(
        $directory,
        $subjectsDirectory,
        $subjectId,
        $localPath
    );

    if ($relativePath === null) {
        return h(cover_placeholder_url());
    }

    $query = http_build_query(
        [
            'id' => $subjectId,
            'p' => $relativePath,
        ],
        '',
        '&',
        PHP_QUERY_RFC3986
    );

    return h('cover.php?' . $query);
}

/**
 * A stable authenticated placeholder URL.
 *
 * Subject ID 1 is only a syntactically valid ID here. An empty path makes the
 * existing cover.php handler return the configured fallback image.
 */
function cover_placeholder_url(): string
{
    return 'cover.php?id=1&p=';
}

function cover_onerror_attr(): string
{
    return ' onerror="this.onerror=null;this.src=\'cover.php?id=1&amp;p=\'"';
}

/**
 * Legacy helper retained for maintenance compatibility.
 */
function cover_fallback_url(
    string $directory,
    string $publicPath,
    string $fallback
): string {
    static $fallbackCache = [];

    $key = $directory . "\0" . $publicPath . "\0" . $fallback;

    if (array_key_exists($key, $fallbackCache)) {
        return $fallbackCache[$key];
    }

    $fallbackPath = $directory . '/' . $fallback;

    if (cover_file_is_valid($fallbackPath, $directory, $fallback)) {
        return $fallbackCache[$key] = cover_public_url(
            $publicPath,
            $fallback
        );
    }

    return $fallbackCache[$key] = 'static/img/placeholder.svg';
}

function cover_existing_relative_path(
    string $directory,
    string $subjectsDirectory,
    int $subjectId,
    ?string $localPath
): ?string {
    if ($localPath === null || $localPath === '') {
        return null;
    }

    $safe = cover_safe_relative_path(
        $subjectId,
        $localPath,
        $subjectsDirectory
    );

    if ($safe === null) {
        return null;
    }

    return cover_file_is_valid(
        $directory . '/' . $safe,
        $directory,
        $safe
    ) ? $safe : null;
}

function cover_partition_prefix(
    int $subjectId,
    string $subjectsDirectory = 'subjects'
): string {
    $subjectsDirectory = trim($subjectsDirectory, '/');

    $level1 = str_pad(
        (string) intdiv($subjectId, 1000000),
        3,
        '0',
        STR_PAD_LEFT
    );

    $level2 = str_pad(
        (string) intdiv($subjectId % 1000000, 1000),
        3,
        '0',
        STR_PAD_LEFT
    );

    return $subjectsDirectory . '/' . $level1 . '/' . $level2 . '/';
}

function cover_safe_relative_path(
    int $subjectId,
    string $path,
    string $subjectsDirectory = 'subjects'
): ?string {
    $path = trim(
        str_replace('\\', '/', $path),
        '/'
    );

    if (str_starts_with($path, 'covers/')) {
        $path = substr($path, strlen('covers/'));
    }

    if (
        $path === '' ||
        str_contains($path, '..') ||
        preg_match('/[\x00-\x1F\x7F]/', $path)
    ) {
        return null;
    }

    $quotedSubjects = preg_quote(
        trim($subjectsDirectory, '/'),
        '#'
    );

    $quotedPrefix = preg_quote(
        cover_partition_prefix(
            $subjectId,
            $subjectsDirectory
        ),
        '#'
    );

    $namePattern =
        $subjectId .
        '_(?:[A-Za-z0-9_-]+)' .
        '(?:--[a-f0-9]{12}|--[a-f0-9]{64})?' .
        '\.(?:jpg|jpeg|png|webp)';

    if (
        preg_match(
            '#^' . $quotedPrefix . '(' . $namePattern . ')$#i',
            $path
        )
    ) {
        return $path;
    }

    if (
        preg_match(
            '#^' .
            $subjectId .
            '\.(?:jpg|jpeg|png|webp)$#i',
            $path
        )
    ) {
        return $path;
    }

    if (
        preg_match(
            '#^' . $quotedSubjects . '/#',
            $path
        )
    ) {
        return null;
    }

    return null;
}

function cover_file_is_valid(
    string $path,
    ?string $coversDirectory = null,
    ?string $relativePath = null
): bool {
    static $fileCache = [];

    $cacheKey =
        $path .
        "\0" .
        (string) $coversDirectory .
        "\0" .
        (string) $relativePath;

    if (array_key_exists($cacheKey, $fileCache)) {
        return $fileCache[$cacheKey];
    }

    $extension = strtolower(
        pathinfo(
            $relativePath ?? $path,
            PATHINFO_EXTENSION
        )
    );

    if ($extension === 'jpeg') {
        $extension = 'jpg';
    }

    if (
        !in_array(
            $extension,
            ['jpg', 'png', 'webp'],
            true
        )
    ) {
        return $fileCache[$cacheKey] = false;
    }

    if (!is_file($path) || filesize($path) <= 0) {
        return $fileCache[$cacheKey] = false;
    }

    if ($coversDirectory !== null) {
        $coverRoot = cover_cached_realpath(
            $coversDirectory
        );

        $real = realpath($path);

        if (
            $coverRoot === false ||
            $real === false ||
            !str_starts_with(
                $real,
                rtrim(
                    $coverRoot,
                    DIRECTORY_SEPARATOR
                ) . DIRECTORY_SEPARATOR
            )
        ) {
            return $fileCache[$cacheKey] = false;
        }
    }

    return $fileCache[$cacheKey] = true;
}

function cover_cached_realpath(string $path): string|false
{
    static $realpathCache = [];

    if (!array_key_exists($path, $realpathCache)) {
        $realpathCache[$path] = realpath($path);
    }

    return $realpathCache[$path];
}

function cover_public_url(
    string $publicPath,
    string $relativePath
): string {
    $relativePath = implode(
        '/',
        array_map(
            'rawurlencode',
            explode(
                '/',
                trim($relativePath, '/')
            )
        )
    );

    return (
        $publicPath !== ''
            ? $publicPath . '/'
            : ''
    ) . $relativePath;
}
