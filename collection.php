<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/install.php';
require_once __DIR__ . '/includes/collection.php';
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/image.php';

require_login();

$page = max(1, (int) ($_GET['page'] ?? 1));
$perPage = 50;
try {
    $totalItems = count_collections();
    $totalPages = max(1, (int) ceil($totalItems / $perPage));
    $page = min($page, $totalPages);
    $items = list_collections($perPage, ($page - 1) * $perPage);
} catch (Throwable $error) {
    render_setup_error($error);
}
$title = '我的收藏';
require __DIR__ . '/templates/header.php';
?>
<h1>我的收藏</h1>
<div class="grid"><?php foreach ($items as $item): ?><article class="card"><a href="subject.php?id=<?= (int) $item['subject_id'] ?>"><img src="<?= cover_url((int) $item['subject_id'], $item['cover_local_path'] ?? null) ?>" alt=""></a><h2><?= h($item['name_cn'] ?: $item['name']) ?></h2><p><?= h(subject_year($item['date'])) ?> · 我的评分 <?= h($item['my_rating'] ?? '未评分') ?></p><p><?= h($item['watch_progress'] ?? '') ?></p><a href="collection_edit.php?id=<?= (int) $item['subject_id'] ?>">编辑</a></article><?php endforeach; ?></div>
<nav class="pager"><?php if ($page > 1): ?><a href="collection.php?page=<?= $page - 1 ?>">&lt; 上一页</a><?php endif; ?><span>第 <?= $page ?> / <?= $totalPages ?> 页</span><?php if ($page < $totalPages): ?><a href="collection.php?page=<?= $page + 1 ?>">下一页 &gt;</a><?php endif; ?></nav>
<?php require __DIR__ . '/templates/footer.php'; ?>
