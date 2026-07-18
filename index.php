<?php
declare(strict_types=1);
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/collection.php';
require_once __DIR__ . '/includes/image.php';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'collect') { add_collection((int) $_POST['subject_id']); header('Location: index.php'); exit; }
$title = '首页海报墙'; $items = list_anime(); require __DIR__ . '/templates/header.php';
?>
<h1>首页海报墙</h1><div class="grid"><?php foreach ($items as $item): ?><article class="card"><a href="subject.php?id=<?= (int)$item['id'] ?>"><img src="<?= cover_url((int)$item['id'], $item['cover_local_path'] ?? null) ?>" alt=""></a><h2><a href="subject.php?id=<?= (int)$item['id'] ?>"><?= h($item['name_cn'] ?: $item['name']) ?></a></h2><p><?= h($item['name']) ?></p><p><?= h(subject_year($item['date'])) ?> · 评分 <?= h($item['score'] ?? '暂无') ?></p><?php if ($item['collected_subject_id']): ?><span class="badge">已收藏</span><?php else: ?><form method="post"><input type="hidden" name="action" value="collect"><input type="hidden" name="subject_id" value="<?= (int)$item['id'] ?>"><button>加入收藏</button></form><?php endif; ?></article><?php endforeach; ?></div>
<?php require __DIR__ . '/templates/footer.php'; ?>
