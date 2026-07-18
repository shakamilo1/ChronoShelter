<?php

declare(strict_types=1);

require_once __DIR__ . '/auth.php';

function csrf_token(): string
{
    auth_start_session();
    if (empty($_SESSION['chronoshelter_csrf_token'])) {
        $_SESSION['chronoshelter_csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['chronoshelter_csrf_token'];
}

function verify_csrf(?string $token = null): void
{
    auth_start_session();
    $submitted = $token ?? (string) ($_POST['csrf_token'] ?? '');
    $known = (string) ($_SESSION['chronoshelter_csrf_token'] ?? '');
    if ($known === '' || $submitted === '' || !hash_equals($known, $submitted)) {
        http_response_code(403);
        exit('CSRF token validation failed.');
    }
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf_token" value="' . h(csrf_token()) . '">';
}
