<?php

declare(strict_types=1);

require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/install.php';
require_once __DIR__ . '/includes/collection.php';
require_once __DIR__ . '/includes/bangumi.php';
require_once __DIR__ . '/includes/image.php';

require_login();

$filters = normalize_collection_filters($_GET);
$page = max(1, (int) ($_GET['page'] ?? 1));
$perPage = 50;

try {
    $filterOptions = collection_filter_options();
    $totalItems = count_collections($filters);
    $totalPages = max(1, (int) ceil($totalItems / $perPage));
    $page = min($page, $totalPages);
    $items = list_collections($perPage, ($page - 1) * $perPage, $filters);
} catch (Throwable $error) {
    render_setup_error($error);
}

$title = '我的收藏';
require __DIR__ . '/templates/header.php';
?>
<header class="collection-page-header">
    <div>
        <h1>我的收藏</h1>
        <p class="muted">共 <?= number_format($totalItems) ?> 部动画</p>
    </div>
</header>

<form method="get" action="collection.php" class="collection-filters">
    <div class="collection-filter-primary">
        <label class="filter-field filter-search">
            <span>关键词</span>
            <input
                type="search"
                name="q"
                value="<?= h($filters['q']) ?>"
                placeholder="输入作品名、别名、英文名或罗马字"
                autocomplete="off"
            >
        </label>
        <label class="filter-field filter-sort">
            <span>排序</span>
            <select name="sort">
                <?php foreach (collection_sort_options() as $value => $label): ?>
                    <option value="<?= h($value) ?>" <?= $filters['sort'] === $value ? 'selected' : '' ?>><?= h($label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
    </div>

    <div class="collection-filter-grid">
        <label class="filter-field">
            <span>动画年份</span>
            <input type="number" name="year" min="1800" max="2299" inputmode="numeric" value="<?= h($filters['year']) ?>" placeholder="全部">
        </label>

        <label class="filter-field">
            <span>媒体类型</span>
            <select name="media_type">
                <option value="">全部</option>
                <?php foreach ($filterOptions['media_type'] as $value): ?>
                    <option value="<?= h($value) ?>" <?= $filters['media_type'] === $value ? 'selected' : '' ?>><?= h($value) ?></option>
                <?php endforeach; ?>
            </select>
        </label>

        <label class="filter-field">
            <span>字幕组</span>
            <select name="subtitle_group">
                <option value="">全部</option>
                <?php foreach ($filterOptions['subtitle_group'] as $value): ?>
                    <option value="<?= h($value) ?>" <?= $filters['subtitle_group'] === $value ? 'selected' : '' ?>><?= h($value) ?></option>
                <?php endforeach; ?>
            </select>
        </label>

        <label class="filter-field">
            <span>来源网站</span>
            <select name="source_site">
                <option value="">全部</option>
                <?php foreach ($filterOptions['source_site'] as $value): ?>
                    <option value="<?= h($value) ?>" <?= $filters['source_site'] === $value ? 'selected' : '' ?>><?= h($value) ?></option>
                <?php endforeach; ?>
            </select>
        </label>

        <label class="filter-field">
            <span>我的评分至少</span>
            <select name="rating_min">
                <option value="">不限</option>
                <?php for ($rating = 10; $rating >= 1; $rating--): ?>
                    <option value="<?= $rating ?>" <?= $filters['rating_min'] === $rating ? 'selected' : '' ?>><?= $rating ?> 分</option>
                <?php endfor; ?>
            </select>
        </label>

        <label class="filter-field">
            <span>观看进度</span>
            <select name="progress">
                <option value="all" <?= $filters['progress'] === 'all' ? 'selected' : '' ?>>全部</option>
                <option value="filled" <?= $filters['progress'] === 'filled' ? 'selected' : '' ?>>已填写</option>
                <option value="empty" <?= $filters['progress'] === 'empty' ? 'selected' : '' ?>>未填写</option>
            </select>
        </label>

        <label class="filter-field">
            <span>收藏日期从</span>
            <input type="date" name="date_from" value="<?= h($filters['date_from']) ?>">
        </label>

        <label class="filter-field">
            <span>收藏日期至</span>
            <input type="date" name="date_to" value="<?= h($filters['date_to']) ?>">
        </label>
    </div>

    <div class="collection-filter-actions">
        <button type="submit">应用筛选</button>
        <?php if (collection_has_active_filters($filters) || $filters['sort'] !== 'collected_desc'): ?>
            <a class="button-secondary" href="collection.php">清除条件</a>
        <?php endif; ?>
    </div>
</form>

<div class="collection-results-summary">
    <?php if (collection_has_active_filters($filters)): ?>
        找到 <?= number_format($totalItems) ?> 部符合条件的动画
    <?php else: ?>
        按“<?= h(collection_sort_options()[$filters['sort']]) ?>”排列
    <?php endif; ?>
</div>

<?php if ($items): ?>
    <div class="grid collection-grid">
        <?php foreach ($items as $item): ?>
            <?php
            $displayName = trim((string) ($item['name_cn'] ?: $item['name']));
            $originalName = trim((string) ($item['name'] ?? ''));
            $year = subject_year($item['date']);
            ?>
            <article class="card collection-card">
                <a class="collection-cover" href="subject.php?id=<?= (int) $item['subject_id'] ?>">
                    <img src="<?= cover_url((int) $item['subject_id'], $item['cover_local_path'] ?? null) ?>" alt="<?= h($displayName) ?>"<?= cover_onerror_attr() ?>>
                </a>
                <div class="collection-card-body">
                    <h2><a href="subject.php?id=<?= (int) $item['subject_id'] ?>"><?= h($displayName) ?></a></h2>
                    <?php if ($originalName !== '' && $originalName !== $displayName): ?>
                        <p class="collection-original-name" title="<?= h($originalName) ?>"><?= h($originalName) ?></p>
                    <?php endif; ?>

                    <p class="collection-card-facts">
                        <?php if ($year !== ''): ?><span><?= h($year) ?></span><?php endif; ?>
                        <span>我的评分 <?= h($item['my_rating'] ?? '未评分') ?></span>
                        <?php if ($item['score'] !== null): ?><span>Bangumi <?= h($item['score']) ?></span><?php endif; ?>
                    </p>

                    <?php if (!empty($item['collection_date'])): ?>
                        <p class="collection-date">收藏于 <?= h($item['collection_date']) ?></p>
                    <?php endif; ?>

                    <?php if (trim((string) ($item['watch_progress'] ?? '')) !== ''): ?>
                        <p class="collection-progress">进度：<?= h($item['watch_progress']) ?></p>
                    <?php endif; ?>

                    <?php if (!empty($item['media_type']) || !empty($item['subtitle_group']) || !empty($item['source_site'])): ?>
                        <div class="collection-chips">
                            <?php foreach (['media_type', 'subtitle_group', 'source_site'] as $field): ?>
                                <?php if (trim((string) ($item[$field] ?? '')) !== ''): ?>
                                    <span><?= h($item[$field]) ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>

                    <a class="collection-edit-link" href="collection_edit.php?id=<?= (int) $item['subject_id'] ?>">编辑收藏</a>
                </div>
            </article>
        <?php endforeach; ?>
    </div>
<?php else: ?>
    <section class="collection-empty">
        <h2>没有找到符合条件的收藏</h2>
        <p class="muted">可以减少筛选条件，或换一个作品名、英文名、罗马字或别名。</p>
        <a class="button-secondary" href="collection.php">查看全部收藏</a>
    </section>
<?php endif; ?>

<?php if ($totalPages > 1): ?>
    <nav class="pager" aria-label="收藏分页">
        <?php if ($page > 1): ?><a href="<?= h(collection_url($filters, $page - 1)) ?>">&lt; 上一页</a><?php endif; ?>
        <span>第 <?= $page ?> / <?= $totalPages ?> 页</span>
        <?php if ($page < $totalPages): ?><a href="<?= h(collection_url($filters, $page + 1)) ?>">下一页 &gt;</a><?php endif; ?>
    </nav>
<?php endif; ?>

<?php require __DIR__ . '/templates/footer.php'; ?>
