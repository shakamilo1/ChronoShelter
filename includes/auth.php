<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function auth_start_session(): void
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
}

function auth_enabled(): bool
{
    return (bool) (app_config()['auth']['enabled'] ?? true);
}

function is_logged_in(): bool
{
    auth_start_session();
    if (!auth_enabled()) {
        return true;
    }
    return isset($_SESSION['chronoshelter_logged_in']) && $_SESSION['chronoshelter_logged_in'] === true;
}

function auth_base_path(): string
{
    $scriptName = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? ''));
    $directory = rtrim(str_replace('\\', '/', dirname($scriptName)), '/');
    return $directory === '' || $directory === '.' ? '' : $directory;
}

/**
 * Return the current application target without the deployment directory.
 *
 * A request for /chronoshelter/subject.php?id=1 becomes subject.php?id=1.
 * The home page uses ./ so browsers do not expose index.php in normal links.
 */
function auth_current_target(): string
{
    $script = basename(str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? 'index.php')));
    $target = $script === '' || $script === 'index.php' ? './' : $script;
    $query = parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_QUERY);
    if (is_string($query) && $query !== '') {
        $target .= '?' . $query;
    }
    return $target;
}

/**
 * Normalize and validate a post-login target.
 *
 * Legacy absolute paths containing the application's mount directory are
 * accepted, but the prefix is stripped exactly once. External URLs, protocol-
 * relative URLs, traversal and unknown PHP entrypoints are rejected.
 */
function auth_safe_target(string $target): string
{
    $target = trim($target);
    if ($target === '' || str_contains($target, "\0") || str_contains($target, '\\')) {
        return './';
    }

    $parts = parse_url($target);
    if ($parts === false || isset($parts['scheme']) || isset($parts['host']) || isset($parts['user']) || isset($parts['pass'])) {
        return './';
    }

    $path = rawurldecode((string) ($parts['path'] ?? ''));
    if (str_starts_with($path, '//') || str_contains($path, '..')) {
        return './';
    }

    $basePath = auth_base_path();
    if ($basePath !== '' && ($path === $basePath || str_starts_with($path, $basePath . '/'))) {
        $path = substr($path, strlen($basePath));
    }
    $path = ltrim($path, '/');

    if ($path === '' || $path === '.' || $path === './' || $path === 'index.php') {
        $path = './';
    } else {
        $allowed = ['subject.php', 'collection.php', 'collection_edit.php', 'admin.php'];
        if (!in_array($path, $allowed, true)) {
            return './';
        }
    }

    $query = (string) ($parts['query'] ?? '');
    return $path . ($query !== '' ? '?' . $query : '');
}

function require_login(): void
{
    if (is_logged_in()) {
        return;
    }
    header('Location: login.php?next=' . rawurlencode(auth_current_target()));
    exit;
}

function login_user(string $username, string $password): bool
{
    auth_start_session();
    $auth = app_config()['auth'] ?? [];
    $expectedUser = (string) ($auth['username'] ?? 'admin');
    $passwordHash = (string) ($auth['password_hash'] ?? '');
    if ($expectedUser !== $username || $passwordHash === '' || !password_verify($password, $passwordHash)) {
        return false;
    }
    session_regenerate_id(true);
    $_SESSION['chronoshelter_logged_in'] = true;
    $_SESSION['chronoshelter_username'] = $expectedUser;
    return true;
}

function logout_user(): void
{
    auth_start_session();
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000, $params['path'], $params['domain'], $params['secure'], $params['httponly']);
    }
    session_destroy();
}
