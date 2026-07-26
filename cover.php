<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/image.php';

/**
 * Private cover image endpoint.
 *
 * The browser supplies:
 *   id = Bangumi subject ID
 *   p  = the database cover_cache.local_path value
 *
 * This endpoint never downloads remote files and never guesses filenames.
 */

$method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));

if (!in_array($method, ['GET', 'HEAD'], true)) {
    header('Allow: GET, HEAD');
    http_response_code(405);
    exit;
}

/*
 * Image requests must not redirect to login.php, because the browser would
 * receive an HTML login page where an image is expected.
 */
if (!is_logged_in()) {
    http_response_code(403);
    header('Content-Type: text/plain; charset=UTF-8');
    header('Cache-Control: no-store');

    if ($method !== 'HEAD') {
        echo 'Forbidden';
    }

    exit;
}

/*
 * Release the PHP session lock immediately so dozens of cover requests can
 * load concurrently instead of waiting for one another.
 */
if (session_status() === PHP_SESSION_ACTIVE) {
    session_write_close();
}

$subjectId = filter_input(
    INPUT_GET,
    'id',
    FILTER_VALIDATE_INT,
    [
        'options' => [
            'min_range' => 1,
        ],
    ]
);

$localPath = $_GET['p'] ?? '';

if (
    $subjectId === false ||
    $subjectId === null ||
    !is_string($localPath)
) {
    http_response_code(400);
    header('Content-Type: text/plain; charset=UTF-8');
    header('Cache-Control: no-store');

    if ($method !== 'HEAD') {
        echo 'Bad Request';
    }

    exit;
}

$config = app_config()['covers'] ?? [];

$coversDirectory = rtrim(
    (string) ($config['directory'] ?? (__DIR__ . '/covers')),
    "/\\"
);

$subjectsDirectory = trim(
    (string) ($config['subjects_directory'] ?? 'subjects'),
    '/'
);

$fallbackFilename = basename(
    str_replace(
        '\\',
        '/',
        (string) ($config['fallback'] ?? ($config['placeholder'] ?? 'logo.png'))
    )
);

if (
    $fallbackFilename === '' ||
    $fallbackFilename === '.' ||
    $fallbackFilename === '..'
) {
    $fallbackFilename = 'logo.png';
}

/**
 * Confirm that a file is a normal file inside the configured covers root.
 *
 * Every path component is checked so symbolic links cannot escape or redirect
 * the request, even when the final real path appears to remain inside covers.
 */
function private_cover_resolve_file(
    string $coversDirectory,
    string $relativePath
): ?string {
    $relativePath = trim(
        str_replace('\\', '/', $relativePath),
        '/'
    );

    if (
        $relativePath === '' ||
        str_contains($relativePath, "\0") ||
        preg_match('/[\x00-\x1F\x7F]/', $relativePath) ||
        str_contains($relativePath, '..')
    ) {
        return null;
    }

    $parts = explode('/', $relativePath);

    foreach ($parts as $part) {
        if (
            $part === '' ||
            $part === '.' ||
            $part === '..'
        ) {
            return null;
        }
    }

    if (is_link($coversDirectory)) {
        return null;
    }

    $rootRealPath = realpath($coversDirectory);

    if ($rootRealPath === false || !is_dir($rootRealPath)) {
        return null;
    }

    $currentPath = $rootRealPath;

    foreach ($parts as $part) {
        $currentPath .= DIRECTORY_SEPARATOR . $part;

        if (is_link($currentPath)) {
            return null;
        }
    }

    if (!is_file($currentPath)) {
        return null;
    }

    $realPath = realpath($currentPath);

    if ($realPath === false) {
        return null;
    }

    $rootPrefix = rtrim(
        $rootRealPath,
        DIRECTORY_SEPARATOR
    ) . DIRECTORY_SEPARATOR;

    if (!str_starts_with($realPath, $rootPrefix)) {
        return null;
    }

    $fileSize = filesize($realPath);

    if ($fileSize === false || $fileSize <= 0) {
        return null;
    }

    return $realPath;
}

/**
 * Determine the response MIME type from the already validated file extension.
 *
 * Full MIME, structure, dimensions and SHA validation remain in the offline
 * cover verification/import tools, not in this web request hot path.
 */
function private_cover_mime_type(string $path): ?string
{
    $extension = strtolower(
        pathinfo($path, PATHINFO_EXTENSION)
    );

    return match ($extension) {
        'jpg', 'jpeg' => 'image/jpeg',
        'png'         => 'image/png',
        'webp'        => 'image/webp',
        default       => null,
    };
}

$isFallback = false;

$safeRelativePath = cover_safe_relative_path(
    (int) $subjectId,
    $localPath,
    $subjectsDirectory
);

$filePath = null;

if ($safeRelativePath !== null) {
    $filePath = private_cover_resolve_file(
        $coversDirectory,
        $safeRelativePath
    );
}

/*
 * Invalid, missing or outdated database mappings use the local logo.
 */
if ($filePath === null) {
    $isFallback = true;

    $fallbackExtension = strtolower(
        pathinfo($fallbackFilename, PATHINFO_EXTENSION)
    );

    if (
        !in_array(
            $fallbackExtension,
            ['jpg', 'jpeg', 'png', 'webp'],
            true
        )
    ) {
        $fallbackFilename = 'logo.png';
    }

    $filePath = private_cover_resolve_file(
        $coversDirectory,
        $fallbackFilename
    );
}

/*
 * If covers/logo.png is also unavailable, return the public SVG placeholder.
 */
if ($filePath === null) {
    header('Location: static/img/placeholder.svg', true, 302);
    header('Cache-Control: private, max-age=60');
    exit;
}

$mimeType = private_cover_mime_type($filePath);

if ($mimeType === null) {
    http_response_code(415);
    header('Content-Type: text/plain; charset=UTF-8');
    header('Cache-Control: no-store');

    if ($method !== 'HEAD') {
        echo 'Unsupported Media Type';
    }

    exit;
}

$fileSize = filesize($filePath);
$modifiedTime = filemtime($filePath);

if (
    $fileSize === false ||
    $fileSize <= 0 ||
    $modifiedTime === false
) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=UTF-8');
    header('Cache-Control: no-store');

    if ($method !== 'HEAD') {
        echo 'Not Found';
    }

    exit;
}

/*
 * The ETag is generated from inexpensive file metadata.
 * It does not read or hash the complete image on every request.
 */
$etag = '"' . hash(
    'sha256',
    $filePath . "\0" . $fileSize . "\0" . $modifiedTime
) . '"';

header('Content-Type: ' . $mimeType);
header('Content-Length: ' . $fileSize);
header('Content-Disposition: inline');
header('X-Content-Type-Options: nosniff');
header('ETag: ' . $etag);
header(
    'Last-Modified: ' .
    gmdate('D, d M Y H:i:s', $modifiedTime) .
    ' GMT'
);

if ($isFallback) {
    /*
     * Do not cache the fallback permanently because logo.png may be replaced.
     */
    header('Cache-Control: private, max-age=300');
} else {
    /*
     * Cover filenames are versioned through the database mapping, so a mapped
     * image can be cached for a long time.
     */
    header(
        'Cache-Control: private, max-age=31536000, immutable'
    );
}

$ifNoneMatch = trim(
    (string) ($_SERVER['HTTP_IF_NONE_MATCH'] ?? '')
);

if ($ifNoneMatch !== '' && $ifNoneMatch === $etag) {
    http_response_code(304);
    exit;
}

$ifModifiedSince = trim(
    (string) ($_SERVER['HTTP_IF_MODIFIED_SINCE'] ?? '')
);

if ($ifNoneMatch === '' && $ifModifiedSince !== '') {
    $clientTime = strtotime($ifModifiedSince);

    if (
        $clientTime !== false &&
        $clientTime >= $modifiedTime
    ) {
        http_response_code(304);
        exit;
    }
}

if ($method === 'HEAD') {
    exit;
}

$handle = fopen($filePath, 'rb');

if ($handle === false) {
    http_response_code(500);
    exit;
}

fpassthru($handle);
fclose($handle);
exit;