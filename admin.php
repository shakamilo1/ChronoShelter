<?php
declare(strict_types=1);
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/database.php';
require_login();
function count_table(PDO $db,string $table): int { return (int)$db->query('SELECT COUNT(*) FROM `'.$table.'`')->fetchColumn(); }
$title='管理'; $stats=['subjects'=>count_table(db_public(),'subjects'),'episodes'=>count_table(db_public(),'episodes'),'collections'=>count_table(db_library(),'collections')]; require __DIR__.'/templates/header.php';
?>
<h1>管理页面</h1><dl class="stats"><dt>subjects数量</dt><dd><?= h($stats['subjects']) ?></dd><dt>episodes数量</dt><dd><?= h($stats['episodes']) ?></dd><dt>收藏数量</dt><dd><?= h($stats['collections']) ?></dd></dl><button disabled>更新 Bangumi 数据</button><p class="notice">第一版请在 NAS 或本地手动运行：<code>python importer/archive_update.py</code>（当前仓库实际路径也保留 <code>tools/archive_update.py</code>）。</p>
<?php require __DIR__.'/templates/footer.php'; ?>
