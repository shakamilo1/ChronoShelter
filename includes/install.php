<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function render_setup_error(Throwable $error): never
{
    http_response_code(500);
    $message = $error->getMessage();
    $looksLikeSchema = str_contains($message, 'Base table or view not found') || str_contains($message, "doesn't exist") || str_contains($message, 'Unknown database');
    require dirname(__DIR__) . '/templates/header.php';
    echo '<section class="setup-error">';
    echo '<h1>数据库尚未初始化</h1>';
    if ($looksLikeSchema) {
        echo '<p>请先创建 <code>chrono_bangumi</code> 与 <code>chrono_library</code>，然后执行以下初始化脚本：</p>';
        echo '<pre>mysql -u root -p chrono_bangumi &lt; database/chrono_bangumi_schema.sql' . "\n" . 'mysql -u root -p chrono_library &lt; database/chrono_library_schema.sql</pre>';
        echo '<p>公共 Bangumi Archive 数据表创建后，还需要用 Python importer 导入 Archive 数据。</p>';
    } else {
        echo '<p>数据库连接或查询失败。请检查 <code>config/config.php</code> 中的 MariaDB 主机、用户、密码和数据库名。</p>';
    }
    echo '<p>详细部署流程见 <a href="docs/deployment.md">docs/deployment.md</a>。部署检查可访问 <a href="install_check.php">install_check.php</a>。</p>';
    echo '<details><summary>错误详情</summary><pre>' . h($message) . '</pre></details>';
    echo '</section>';
    require dirname(__DIR__) . '/templates/footer.php';
    exit;
}

function required_tables(): array
{
    return [
        'public' => ['subjects', 'episodes', 'persons', 'characters', 'subject_persons', 'subject_characters', 'subject_relations'],
        'library' => ['collections', 'cover_cache'],
    ];
}

function table_exists(PDO $db, string $database, string $table): bool
{
    $stmt = $db->prepare('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db AND table_name = :table');
    $stmt->execute(['db' => $database, 'table' => $table]);
    return (int) $stmt->fetchColumn() > 0;
}

function required_columns(): array
{
    return [
        'library' => [
            'cover_cache' => ['subject_id', 'status', 'remote_filename', 'source_url', 'local_path', 'content_type', 'file_size', 'sha256', 'error', 'updated_at'],
        ],
    ];
}

function column_exists(PDO $db, string $database, string $table, string $column): bool
{
    $stmt = $db->prepare('SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = :db AND table_name = :table AND column_name = :column');
    $stmt->execute(['db' => $database, 'table' => $table, 'column' => $column]);
    return (int) $stmt->fetchColumn() > 0;
}

function required_indexes(): array
{
    return [
        'public' => [
            'subjects' => ['idx_subjects_type_date_id', 'idx_subjects_type_score_id'],
        ],
    ];
}

function index_exists(PDO $db, string $database, string $table, string $index): bool
{
    $stmt = $db->prepare('SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = :db AND table_name = :table AND index_name = :index');
    $stmt->execute(['db' => $database, 'table' => $table, 'index' => $index]);
    return (int) $stmt->fetchColumn() > 0;
}
