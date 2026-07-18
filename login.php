<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/csrf.php';

if (is_logged_in()) {
    header('Location: index.php');
    exit;
}

$error = '';
$next = (string) ($_GET['next'] ?? $_POST['next'] ?? 'index.php');
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    if (login_user((string) ($_POST['username'] ?? ''), (string) ($_POST['password'] ?? ''))) {
        header('Location: ' . (str_starts_with($next, '/') ? $next : 'index.php'));
        exit;
    }
    $error = '用户名或密码错误。';
}
$title = '登录';
require __DIR__ . '/templates/header.php';
?>
<h1>登录 ChronoShelter</h1>
<?php if ($error): ?><p class="error"><?= h($error) ?></p><?php endif; ?>
<form method="post" class="form">
    <?= csrf_field() ?>
    <input type="hidden" name="next" value="<?= h($next) ?>">
    <label>用户名 <input name="username" autocomplete="username" required></label>
    <label>密码 <input type="password" name="password" autocomplete="current-password" required></label>
    <button>登录</button>
</form>
<?php require __DIR__ . '/templates/footer.php'; ?>
