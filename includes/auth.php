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

function require_login(): void
{
    if (is_logged_in()) {
        return;
    }
    $target = $_SERVER['REQUEST_URI'] ?? 'index.php';
    header('Location: login.php?next=' . rawurlencode($target));
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
