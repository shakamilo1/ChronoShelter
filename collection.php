<?php
declare(strict_types=1);
require_once __DIR__ . '/includes/collection.php'; require_once __DIR__ . '/includes/bangumi.php'; require_once __DIR__ . '/includes/image.php';
$title='我的收藏'; $items=list_collections(); require __DIR__.'/templates/header.php';
?>
<h1>我的收藏</h1><div class="grid"><?php foreach($items as $item): ?><article class="card"><a href="subject.php?id=<?= (int)$item['subject_id'] ?>"><img src="<?= cover_url((int)$item['subject_id'], $item['cover_local_path'] ?? null) ?>" alt=""></a><h2><?= h($item['name_cn'] ?: $item['name']) ?></h2><p><?= h(subject_year($item['date'])) ?> · 我的评分 <?= h($item['my_rating'] ?? '未评分') ?></p><p><?= h($item['watch_progress'] ?? '') ?></p><a href="collection_edit.php?id=<?= (int)$item['subject_id'] ?>">编辑</a></article><?php endforeach; ?></div>
<?php require __DIR__.'/templates/footer.php'; ?>
