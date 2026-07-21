<?php

declare(strict_types=1);

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
    $filename = $subjectId . '.jpg';
    $absolutePath = dirname(__DIR__) . '/covers/' . $filename;

    if (is_file($absolutePath) && filesize($absolutePath) > 0) {
        return 'covers/' . $filename;
    }

    return 'static/img/placeholder.svg';
}
