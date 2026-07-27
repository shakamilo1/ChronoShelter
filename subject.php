<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/install.php';
require_once __DIR__ . '/includes/csrf.php';
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/subject_detail.php';
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

$subject = get_subject($id);
if (!$subject) {
    http_response_code(404);
    exit('Subject not found');
}

$collection = get_collection($id);
$title = $subject['name_cn'] ?: $subject['name'];
$episodes = get_subject_episodes($id);
$persons = get_subject_persons($id);
$characters = get_subject_characters($id);
$relations = get_subject_relations($id);

require __DIR__ . '/templates/header.php';
?>
<section class="subject-hero">
<img class="poster" src="<?= cover_url($id, $subject['cover_local_path'] ?? null) ?>" alt=""<?= cover_onerror_attr() ?> >
<div class="subject-main"><h1><?= h($subject['name_cn'] ?: $subject['name']) ?></h1><h2><?= h($subject['name']) ?></h2><div class="summary-preview"><?= nl2br(h($subject['summary'])) ?></div>
<div class="info-grid"><div>类型 <?= h(subject_platform_name((int)$subject['platform'])) ?></div><div>首播 <?= h($subject['date']) ?></div><div>话数 <?= count($episodes) ?></div><div>评分 <?= h($subject['score']) ?></div><div>排名 <?= h($subject['rank']) ?></div><div>收藏 <?= h(subject_favorite_count($subject['favorite'])) ?></div></div></div>
<aside class="score-card"><h3>公共评分</h3><strong><?= h($subject['score']) ?>/10</strong><?php if (!$collection || !$collection['collected']): ?><form method="post"><?= csrf_field() ?><input type="hidden" name="action" value="collect"><button>加入收藏</button></form><?php endif; ?></aside>
</section>
<section class="panel"><h2>作品简介</h2><p><?= nl2br(h($subject['summary'])) ?></p></section>
<section class="panel"><h2>剧集资料</h2><div class="episode-list"><?php foreach ($episodes as $ep): ?><a href="episode.php?id=<?= (int)$ep['id'] ?>"><?= h($ep['sort']) ?>. <?= h($ep['name_cn'] ?: $ep['name']) ?></a><?php endforeach; ?></div></section>
<section class="panel"><h2>标签</h2><div class="tags"><?php foreach(subject_tags($subject['tags']) as $tag): ?><span><?= h($tag) ?></span><?php endforeach; ?></div></section>
<section class="panel"><h2>角色</h2><div class="character-grid"><?php foreach($characters as $character): ?><div class="character-card"><?= h($character['name']) ?></div><?php endforeach; ?></div></section>
<section class="panel"><h2>关联作品</h2><?php foreach($relations as $relation): ?><a href="subject.php?id=<?= (int)$relation['id'] ?>"><?= h($relation['name_cn'] ?: $relation['name']) ?></a> <?php endforeach; ?></section>
<section class="panel"><h2>制作信息</h2><div class="staff-grid"><?php foreach($persons as $person): ?><div><?= h($person['name']) ?><small><?= h($person['position']) ?></small></div><?php endforeach; ?></div></section>
<?php require __DIR__ . '/templates/footer.php'; ?>