<?php

declare(strict_types=1);

return [
    'db' => [
        'host' => getenv('CHRONOSHELTER_DB_HOST') ?: '127.0.0.1',
        'port' => (int) (getenv('CHRONOSHELTER_DB_PORT') ?: 3306),
        'user' => getenv('CHRONOSHELTER_DB_USER') ?: 'chronoshelter',
        'password' => getenv('CHRONOSHELTER_DB_PASSWORD') ?: 'change-me',
        'public_database' => getenv('CHRONOSHELTER_PUBLIC_DB_NAME') ?: 'chrono_bangumi',
        'library_database' => getenv('CHRONOSHELTER_LIBRARY_DB_NAME') ?: 'chrono_library',
        'charset' => 'utf8mb4',
    ],
    'covers' => [
        'directory' => dirname(__DIR__) . '/covers',
        'public_path' => 'covers',
        'api_url' => 'https://api.bgm.tv/v0/subjects/%d/image?type=large',
        'no_icon_url' => 'https://lain.bgm.tv/img/no_icon_subject.png',
    ],
];
