<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/install.php';
require_once __DIR__ . '/includes/csrf.php';
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/collection.php';
require_once __DIR__ . '/includes/image.php';

require_login();

$id = (int) ($_GET['id'] ?? 0);
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'collect') {
    verify_csrf();
    add_collection($id);
    header('Location: subject.php?id=' . $id);
    exit;
}
try {
    $subject = get_subject($id);
} catch (Throwable $error) {
    render_setup_error($error);
}
if (!$subject) {
    http_response_code(404);
    exit('Subject not found');
}
$collection = get_collection($id);
$title = $subject['name_cn'] ?: $subject['name'];
require __DIR__ . '/templates/header.php';
?>
<section class="detail"><img class="poster" src="<?= cover_url($id, $subject['cover_local_path'] ?? null) ?>" alt=""<?= cover_onerror_attr() ?>><div><h1><?= h($subject['name_cn']) ?></h1><h2><?= h($subject['name']) ?></h2><p><a href="collection_edit.php?id=<?= $id ?>">编辑收藏</a></p><?php if ($collection && $collection['collected']): ?><span class="badge">已收藏</span><?php else: ?><form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="collect"><button>加入收藏</button></form><?php endif; ?></div></section>
<table class="meta"><tr><th>类型</th><td>动画</td></tr><tr><th>放送日期</th><td><?= h($subject['date']) ?></td></tr><tr><th>话数</th><td><?= h(get_episodes_count($id)) ?></td></tr><tr><th>评分</th><td><?= h($subject['score']) ?></td></tr><tr><th>收藏人数</th><td><?= h(subject_favorite_count($subject['favorite'])) ?></td></tr><tr><th>标签</th><td><?= h(implode(' / ', subject_tags($subject['tags']))) ?></td></tr><tr><th>简介</th><td><?= nl2br(h($subject['summary'])) ?></td></tr></table>
<h2>制作人员</h2><ul class="cols"><?php foreach (get_subject_persons($id) as $p): ?><li><?= h($p['name']) ?> <small>#<?= h($p['position']) ?></small></li><?php endforeach; ?></ul>
<h2>角色</h2><ul class="cols"><?php foreach (get_subject_characters($id) as $c): ?><li><?= h($c['name']) ?></li><?php endforeach; ?></ul>
<?php require __DIR__ . '/templates/footer.php'; ?>
