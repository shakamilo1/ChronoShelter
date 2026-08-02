<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function get_collection(int $subjectId): ?array
{
    $stmt = db_library()->prepare('SELECT * FROM collections WHERE subject_id = :id');
    $stmt->execute(['id' => $subjectId]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function add_collection(int $subjectId): void
{
    $sql = 'INSERT INTO collections (subject_id, collected, collection_date)
            VALUES (:id, TRUE, CURRENT_DATE)
            ON DUPLICATE KEY UPDATE collected = TRUE, collection_date = COALESCE(collection_date, CURRENT_DATE), updated_at = CURRENT_TIMESTAMP';
    db_library()->prepare($sql)->execute(['id' => $subjectId]);
}

function save_collection(array $data): void
{
    $sql = 'INSERT INTO collections (subject_id, collected, collection_date, media_type, subtitle_group, source_site, my_rating, notes, watch_progress)
            VALUES (:subject_id, :collected, :collection_date, :media_type, :subtitle_group, :source_site, :my_rating, :notes, :watch_progress)
            ON DUPLICATE KEY UPDATE collected = VALUES(collected), collection_date = VALUES(collection_date), media_type = VALUES(media_type),
                subtitle_group = VALUES(subtitle_group), source_site = VALUES(source_site), my_rating = VALUES(my_rating), notes = VALUES(notes),
                watch_progress = VALUES(watch_progress), updated_at = CURRENT_TIMESTAMP';
    db_library()->prepare($sql)->execute($data);
}

function collection_sort_definitions(): array
{
    return [
        'collected_desc' => [
            'label' => '最近收藏',
            'sql' => 'c.collection_date IS NULL ASC, c.collection_date DESC, c.updated_at DESC, c.subject_id DESC',
        ],
        'collected_asc' => [
            'label' => '最早收藏',
            'sql' => 'c.collection_date IS NULL ASC, c.collection_date ASC, c.updated_at ASC, c.subject_id ASC',
        ],
        'updated_desc' => [
            'label' => '最近修改',
            'sql' => 'c.updated_at DESC, c.subject_id DESC',
        ],
        'rating_desc' => [
            'label' => '我的评分：高到低',
            'sql' => 'c.my_rating IS NULL ASC, c.my_rating DESC, c.subject_id DESC',
        ],
        'rating_asc' => [
            'label' => '我的评分：低到高',
            'sql' => 'c.my_rating IS NULL ASC, c.my_rating ASC, c.subject_id ASC',
        ],
        'year_desc' => [
            'label' => '动画年份：新到旧',
            'sql' => 's.date IS NULL ASC, s.date DESC, c.subject_id DESC',
        ],
        'year_asc' => [
            'label' => '动画年份：旧到新',
            'sql' => 's.date IS NULL ASC, s.date ASC, c.subject_id ASC',
        ],
        'name_cn_asc' => [
            'label' => '中文名',
            'sql' => "COALESCE(NULLIF(s.name_cn, ''), s.name) ASC, c.subject_id ASC",
        ],
        'name_asc' => [
            'label' => '日文名',
            'sql' => "COALESCE(NULLIF(s.name, ''), s.name_cn) ASC, c.subject_id ASC",
        ],
        'score_desc' => [
            'label' => 'Bangumi 评分：高到低',
            'sql' => 's.score IS NULL ASC, s.score DESC, c.subject_id DESC',
        ],
    ];
}

function collection_sort_options(): array
{
    $options = [];
    foreach (collection_sort_definitions() as $key => $definition) {
        $options[$key] = $definition['label'];
    }
    return $options;
}

function collection_string_filter(mixed $value, int $maxLength = 255): string
{
    if (!is_scalar($value)) {
        return '';
    }

    $value = trim((string) $value);
    if ($value === '') {
        return '';
    }

    if (function_exists('mb_substr')) {
        return mb_substr($value, 0, $maxLength, 'UTF-8');
    }

    return substr($value, 0, $maxLength);
}

function collection_date_filter(mixed $value): string
{
    $value = collection_string_filter($value, 10);
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $value, $match)) {
        return '';
    }

    return checkdate((int) $match[2], (int) $match[3], (int) $match[1]) ? $value : '';
}

function normalize_collection_filters(array $input): array
{
    $sortDefinitions = collection_sort_definitions();
    $sort = collection_string_filter($input['sort'] ?? '', 32);
    if (!isset($sortDefinitions[$sort])) {
        $sort = 'collected_desc';
    }

    $year = collection_string_filter($input['year'] ?? '', 4);
    if (!preg_match('/^(18|19|20|21|22)\d{2}$/', $year)) {
        $year = '';
    }

    $ratingMin = filter_var(
        $input['rating_min'] ?? null,
        FILTER_VALIDATE_INT,
        ['options' => ['min_range' => 1, 'max_range' => 10]]
    );
    if ($ratingMin === false) {
        $ratingMin = null;
    }

    $progress = collection_string_filter($input['progress'] ?? '', 16);
    if (!in_array($progress, ['all', 'filled', 'empty'], true)) {
        $progress = 'all';
    }

    return [
        'q' => collection_string_filter($input['q'] ?? '', 200),
        'year' => $year,
        'media_type' => collection_string_filter($input['media_type'] ?? '', 64),
        'subtitle_group' => collection_string_filter($input['subtitle_group'] ?? '', 255),
        'source_site' => collection_string_filter($input['source_site'] ?? '', 255),
        'rating_min' => $ratingMin,
        'date_from' => collection_date_filter($input['date_from'] ?? ''),
        'date_to' => collection_date_filter($input['date_to'] ?? ''),
        'progress' => $progress,
        'sort' => $sort,
    ];
}

function collection_like_pattern(string $value): string
{
    $escaped = str_replace(['\\', '%', '_'], ['\\\\', '\\%', '\\_'], $value);
    return '%' . $escaped . '%';
}

function collection_query_parts(array $filters): array
{
    $filters = normalize_collection_filters($filters);
    $where = [
        'c.collected = TRUE',
        's.type = 2',
    ];
    $params = [];

    if ($filters['q'] !== '') {
        $pattern = collection_like_pattern($filters['q']);
        $where[] = "(s.name LIKE :keyword_name ESCAPE '\\\\'
                    OR s.name_cn LIKE :keyword_name_cn ESCAPE '\\\\'
                    OR s.infobox LIKE :keyword_infobox ESCAPE '\\\\')";
        $params['keyword_name'] = $pattern;
        $params['keyword_name_cn'] = $pattern;
        $params['keyword_infobox'] = $pattern;
    }

    if ($filters['year'] !== '') {
        $where[] = 's.date LIKE :year_prefix';
        $params['year_prefix'] = $filters['year'] . '%';
    }

    foreach (['media_type', 'subtitle_group', 'source_site'] as $field) {
        if ($filters[$field] !== '') {
            $where[] = 'c.' . $field . ' = :' . $field;
            $params[$field] = $filters[$field];
        }
    }

    if ($filters['rating_min'] !== null) {
        $where[] = 'c.my_rating >= :rating_min';
        $params['rating_min'] = $filters['rating_min'];
    }

    if ($filters['date_from'] !== '') {
        $where[] = 'c.collection_date >= :date_from';
        $params['date_from'] = $filters['date_from'];
    }

    if ($filters['date_to'] !== '') {
        $where[] = 'c.collection_date <= :date_to';
        $params['date_to'] = $filters['date_to'];
    }

    if ($filters['progress'] === 'filled') {
        $where[] = "NULLIF(TRIM(c.watch_progress), '') IS NOT NULL";
    } elseif ($filters['progress'] === 'empty') {
        $where[] = "NULLIF(TRIM(c.watch_progress), '') IS NULL";
    }

    $sortDefinitions = collection_sort_definitions();

    return [
        'filters' => $filters,
        'where' => implode("\n                AND ", $where),
        'params' => $params,
        'order_by' => $sortDefinitions[$filters['sort']]['sql'],
    ];
}

function bind_collection_params(PDOStatement $stmt, array $params): void
{
    foreach ($params as $name => $value) {
        $stmt->bindValue(':' . $name, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
    }
}

function count_collections(array $filters = []): int
{
    $publicDb = db_identifier(public_database_name());
    $parts = collection_query_parts($filters);
    $sql = 'SELECT COUNT(*)
            FROM collections c FORCE INDEX (idx_collections_collected)
            STRAIGHT_JOIN ' . $publicDb . '.subjects s FORCE INDEX (PRIMARY)
                ON s.id = c.subject_id
            WHERE ' . $parts['where'];
    $stmt = db_library()->prepare($sql);
    bind_collection_params($stmt, $parts['params']);
    $stmt->execute();
    return (int) $stmt->fetchColumn();
}

function list_collections(int $limit = 50, int $offset = 0, array $filters = []): array
{
    $publicDb = db_identifier(public_database_name());
    $limit = max(1, min(200, $limit));
    $offset = max(0, $offset);
    $parts = collection_query_parts($filters);
    $sql = 'SELECT c.*, s.name, s.name_cn, s.date, s.score, cc.local_path AS cover_local_path
            FROM collections c FORCE INDEX (idx_collections_collected)
            STRAIGHT_JOIN ' . $publicDb . '.subjects s FORCE INDEX (PRIMARY)
                ON s.id = c.subject_id
            LEFT JOIN cover_cache cc FORCE INDEX (PRIMARY)
                ON cc.subject_id = c.subject_id AND cc.status = \'cached\'
            WHERE ' . $parts['where'] . '
            ORDER BY ' . $parts['order_by'] . '
            LIMIT :limit OFFSET :offset';
    $stmt = db_library()->prepare($sql);
    bind_collection_params($stmt, $parts['params']);
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function collection_filter_options(): array
{
    $publicDb = db_identifier(public_database_name());
    $options = [];

    foreach (['media_type', 'subtitle_group', 'source_site'] as $column) {
        $sql = 'SELECT DISTINCT TRIM(c.`' . $column . '`) AS value
                FROM collections c FORCE INDEX (idx_collections_collected)
                STRAIGHT_JOIN ' . $publicDb . '.subjects s FORCE INDEX (PRIMARY)
                    ON s.id = c.subject_id
                WHERE c.collected = TRUE
                  AND s.type = 2
                  AND c.`' . $column . '` IS NOT NULL
                  AND TRIM(c.`' . $column . '`) <> \'\'
                ORDER BY value
                LIMIT 200';
        $rows = db_library()->query($sql)->fetchAll(PDO::FETCH_COLUMN);
        $options[$column] = array_values(array_map('strval', $rows));
    }

    return $options;
}

function collection_has_active_filters(array $filters): bool
{
    $filters = normalize_collection_filters($filters);
    return $filters['q'] !== ''
        || $filters['year'] !== ''
        || $filters['media_type'] !== ''
        || $filters['subtitle_group'] !== ''
        || $filters['source_site'] !== ''
        || $filters['rating_min'] !== null
        || $filters['date_from'] !== ''
        || $filters['date_to'] !== ''
        || $filters['progress'] !== 'all';
}

function collection_query_params(array $filters, int $page = 1): array
{
    $filters = normalize_collection_filters($filters);
    $params = [];

    foreach (['q', 'year', 'media_type', 'subtitle_group', 'source_site', 'date_from', 'date_to'] as $key) {
        if ($filters[$key] !== '') {
            $params[$key] = $filters[$key];
        }
    }

    if ($filters['rating_min'] !== null) {
        $params['rating_min'] = $filters['rating_min'];
    }
    if ($filters['progress'] !== 'all') {
        $params['progress'] = $filters['progress'];
    }
    if ($filters['sort'] !== 'collected_desc') {
        $params['sort'] = $filters['sort'];
    }
    if ($page > 1) {
        $params['page'] = $page;
    }

    return $params;
}

function collection_url(array $filters, int $page = 1): string
{
    $query = http_build_query(collection_query_params($filters, $page), '', '&', PHP_QUERY_RFC3986);
    return 'collection.php' . ($query === '' ? '' : '?' . $query);
}
