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

    $totalPages = max(
        1,
        (int) ceil($totalItems / $perPage)
    );

    $page = min($page, $totalPages);

    $items = list_collections(
        $perPage,
        ($page - 1) * $perPage
    );
} catch (Throwable $error) {
    render_setup_error($error);
}

$title = '我的收藏';
require __DIR__ . '/templates/header.php';
?>

<section class="page-heading">
    <div>
        <p class="eyebrow">Personal Collection</p>
        <h1>我的收藏</h1>
        <p class="page-description">
            已经保存到私人动画档案馆的条目。
        </p>
    </div>

    <div class="archive-count">
        <strong><?= number_format($totalItems) ?></strong>
        <span>条收藏记录</span>
    </div>
</section>

<?php if ($items): ?>
<div class="poster-grid" data-archive-grid>
<?php foreach ($items as $index => $item): ?>
    <?php
    $subjectId = (int) $item['subject_id'];

    $displayTitle = trim(
        (string) ($item['name_cn'] ?: $item['name'])
    );

    $originalTitle = trim(
        (string) ($item['name'] ?? '')
    );

    $dateValue = trim(
        (string) ($item['date'] ?? '')
    );

    $timeLabel = (
        $dateValue !== '' &&
        $dateValue !== '0000-00-00'
    )
        ? $dateValue
        : '时间未定';

    $myRating = $item['my_rating'] ?? null;

    $hasRating =
        $myRating !== null &&
        $myRating !== '';

    $progress = trim(
        (string) ($item['watch_progress'] ?? '')
    );

    $allTags = subject_tags(
        isset($item['tags']) ? (string) $item['tags'] : null
    );

    $visibleTags = array_slice($allTags, 0, 3);
    $hiddenTagCount = max(
        0,
        count($allTags) - count($visibleTags)
    );

    $hasLocalCover = !empty($item['cover_local_path']);

    $loadingMode = $index < 16
        ? 'eager'
        : 'lazy';
    ?>

    <article class="poster-card<?= $hasLocalCover ? '' : ' is-placeholder' ?>">
        <a
            class="poster-media"
            href="subject.php?id=<?= $subjectId ?>"
            aria-label="查看 <?= h($displayTitle) ?>"
        >
            <img
                src="<?= cover_url(
                    $subjectId,
                    $item['cover_local_path'] ?? null
                ) ?>"
                alt="<?= h($displayTitle) ?>"
                width="1086"
                height="1448"
                loading="<?= $loadingMode ?>"
                decoding="async"
                <?= $index < 6 ? 'fetchpriority="high"' : '' ?>
                <?= cover_onerror_attr() ?>
            >

            <span class="poster-vignette" aria-hidden="true"></span>

            <span class="poster-badges">
                <span class="status-badge">
                    已收藏
                </span>

                <?php if ($hasRating): ?>
                    <span class="score-badge score-badge-personal">
                        <span aria-hidden="true">★</span>
                        <?= h((string) $myRating) ?>
                    </span>
                <?php endif; ?>
            </span>

            <?php if ($visibleTags): ?>
                <span class="poster-tag-layer" aria-label="标签">
                    <?php foreach ($visibleTags as $tag): ?>
                        <span class="poster-tag">
                            <?= h($tag) ?>
                        </span>
                    <?php endforeach; ?>

                    <?php if ($hiddenTagCount > 0): ?>
                        <span
                            class="poster-tag poster-tag-more"
                            title="另有 <?= $hiddenTagCount ?> 个标签"
                        >
                            +<?= $hiddenTagCount ?>
                        </span>
                    <?php endif; ?>
                </span>
            <?php endif; ?>
        </a>

        <div class="poster-body">
            <h2 class="poster-title">
                <a href="subject.php?id=<?= $subjectId ?>">
                    <?= h($displayTitle) ?>
                </a>
            </h2>

            <?php if (
                $originalTitle !== '' &&
                $originalTitle !== $displayTitle
            ): ?>
                <p class="poster-original">
                    <?= h($originalTitle) ?>
                </p>
            <?php endif; ?>

            <div class="poster-meta">
                <time
                    <?= $dateValue !== ''
                        ? 'datetime="' . h($dateValue) . '"'
                        : '' ?>
                >
                    <?= h($timeLabel) ?>
                </time>
            </div>

            <?php if ($progress !== ''): ?>
                <p class="watch-progress">
                    <?= h($progress) ?>
                </p>
            <?php endif; ?>

            <div class="poster-actions">
                <a
                    class="button button-ghost button-small"
                    href="collection_edit.php?id=<?= $subjectId ?>"
                >
                    编辑收藏
                </a>
            </div>
        </div>
    </article>
<?php endforeach; ?>
</div>
<?php else: ?>
    <section class="empty-state">
        <div class="empty-symbol" aria-hidden="true">◇</div>
        <h2>收藏库还没有内容</h2>
        <p>从动画档案中选择作品，加入你的私人收藏。</p>
        <a class="button button-primary" href="./">
            浏览动画档案
        </a>
    </section>
<?php endif; ?>

<nav class="pager" aria-label="分页">
    <?php if ($page > 1): ?>
        <a
            class="pager-link"
            href="collection.php?page=<?= $page - 1 ?>"
            rel="prev"
        >
            <span aria-hidden="true">←</span>
            上一页
        </a>
    <?php else: ?>
        <span class="pager-link is-disabled">
            <span aria-hidden="true">←</span>
            上一页
        </span>
    <?php endif; ?>

    <span class="pager-current">
        <strong><?= $page ?></strong>
        <span>/</span>
        <?= $totalPages ?>
    </span>

    <?php if ($page < $totalPages): ?>
        <a
            class="pager-link"
            href="collection.php?page=<?= $page + 1 ?>"
            rel="next"
        >
            下一页
            <span aria-hidden="true">→</span>
        </a>
    <?php else: ?>
        <span class="pager-link is-disabled">
            下一页
            <span aria-hidden="true">→</span>
        </span>
    <?php endif; ?>
</nav>

<?php require __DIR__ . '/templates/footer.php'; ?>
