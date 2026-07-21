<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/database.php';
require_once __DIR__ . '/includes/install.php';

$checks = [];
$checks[] = ['PHP', version_compare(PHP_VERSION, '8.4.0', '>='), PHP_VERSION];
$checks[] = ['PDO MySQL', extension_loaded('pdo_mysql'), extension_loaded('pdo_mysql') ? 'loaded' : 'missing'];

$schemaOk = false;
try {
    $public = db_public();
    $library = db_library();
    $checks[] = ['MariaDB public', true, public_database_name()];
    $checks[] = ['MariaDB library', true, library_database_name()];
    $missing = [];
    foreach (required_tables()['public'] as $table) {
        if (!table_exists($public, public_database_name(), $table)) {
            $missing[] = public_database_name() . '.' . $table;
        }
    }
    foreach (required_tables()['library'] as $table) {
        if (!table_exists($library, library_database_name(), $table)) {
            $missing[] = library_database_name() . '.' . $table;
        }
    }
    $schemaOk = $missing === [];
    $checks[] = ['Schema', $schemaOk, $schemaOk ? 'all required tables exist' : 'missing: ' . implode(', ', $missing)];
} catch (Throwable $error) {
    $checks[] = ['MariaDB', false, $error->getMessage()];
    $checks[] = ['Schema', false, 'database connection failed'];
}

$title = '部署检查';
require __DIR__ . '/templates/header.php';
?>
<h1>部署检查</h1>
<p class="notice">部署完成后建议删除或限制访问 <code>install_check.php</code>。</p>
<table class="meta">
<?php foreach ($checks as [$name, $ok, $detail]): ?>
    <tr><th><?= h($name) ?></th><td><strong class="<?= $ok ? 'ok' : 'fail' ?>"><?= $ok ? 'OK' : 'FAIL' ?></strong> <?= h($detail) ?></td></tr>
<?php endforeach; ?>
</table>
<?php if (!$schemaOk): ?>
<section class="setup-error"><h2>初始化提示</h2><pre>mysql -u root -p chrono_bangumi &lt; database/chrono_bangumi_schema.sql
mysql -u root -p chrono_library &lt; database/chrono_library_schema.sql</pre></section>
<?php endif; ?>
<?php require __DIR__ . '/templates/footer.php'; ?>
