<?php

declare(strict_types=1);

function app_config(): array
{
    static $config = null;
    if ($config === null) {
        $configPath = dirname(__DIR__) . '/config.php';
        $examplePath = dirname(__DIR__) . '/config-example.php';
        $config = require (is_file($configPath) ? $configPath : $examplePath);
    }
    return $config;
}

function db_public(): PDO
{
    return db_connection('public_database');
}

function db_library(): PDO
{
    return db_connection('library_database');
}

function db_connection(string $databaseKey): PDO
{
    static $connections = [];
    $config = app_config()['db'];
    $database = $config[$databaseKey] ?? null;
    if (!is_string($database) || $database === '') {
        throw new RuntimeException("Missing database config: {$databaseKey}");
    }
    if (isset($connections[$databaseKey])) {
        return $connections[$databaseKey];
    }
    $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=%s', $config['host'], $config['port'], $database, $config['charset']);
    $connections[$databaseKey] = new PDO($dsn, $config['user'], $config['password'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    return $connections[$databaseKey];
}

function h(mixed $value): string
{
    return htmlspecialchars((string) ($value ?? ''), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function db_identifier(string $identifier): string
{
    if (!preg_match('/^[A-Za-z0-9_]+$/', $identifier)) {
        throw new RuntimeException('Unsafe database identifier.');
    }
    return '`' . $identifier . '`';
}

function public_database_name(): string
{
    return app_config()['db']['public_database'];
}

function library_database_name(): string
{
    return app_config()['db']['library_database'];
}
