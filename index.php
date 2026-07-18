<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/csrf.php';
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/collection.php';
require_once __DIR__ . '/includes/image.php';

require_login();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'collect') {
    verify_csrf();
    add_collection((int) $_POST['subject_id']);
    header('Location: index.php?page=' . max(1, (int) ($_GET['page'] ?? 1)));
    exit;
}

$page = max(1, (int) ($_GET['page'] ?? 1));
$perPage = 50;
$items = list_anime($perPage, ($page - 1) * $perPage);
$title = '首页海报墙';
require __DIR__ . '/templates/header.php';
?>
<h1>首页海报墙</h1>
<div class="grid">
<?php foreach ($items as $item): ?>
    <article class="card">
        <a href="subject.php?id=<?= (int) $item['id'] ?>"><img src="<?= cover_url((int) $item['id'], $item['cover_local_path'] ?? null) ?>" alt=""></a>
        <h2><a href="subject.php?id=<?= (int) $item['id'] ?>"><?= h($item['name_cn'] ?: $item['name']) ?></a></h2>
        <p><?= h($item['name']) ?></p>
        <p><?= h(subject_year($item['date'])) ?> · 评分 <?= h($item['score'] ?? '暂无') ?></p>
        <?php if ($item['collected_subject_id']): ?>
            <span class="badge">已收藏</span>
        <?php else: ?>
            <form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="collect"><input type="hidden" name="subject_id" value="<?= (int) $item['id'] ?>"><button>加入收藏</button></form>
        <?php endif; ?>
    </article>
<?php endforeach; ?>
</div>
<nav class="pager"><?php if ($page > 1): ?><a href="index.php?page=<?= $page - 1 ?>">上一页</a><?php endif; ?><span>第 <?= $page ?> 页</span><?php if (count($items) === $perPage): ?><a href="index.php?page=<?= $page + 1 ?>">下一页</a><?php endif; ?></nav>
<?php require __DIR__ . '/templates/footer.php'; ?>
