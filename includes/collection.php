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

function count_collections(): int
{
    $publicDb = db_identifier(public_database_name());
    $sql = 'SELECT COUNT(*) FROM collections c JOIN ' . $publicDb . '.subjects s ON s.id = c.subject_id WHERE c.collected = TRUE AND s.type = 2';
    return (int) db_library()->query($sql)->fetchColumn();
}

function list_collections(int $limit = 50, int $offset = 0): array
{
    $publicDb = db_identifier(public_database_name());
    $sql = 'SELECT c.*, s.name, s.name_cn, s.date, s.score, cc.local_path AS cover_local_path
            FROM collections c
            JOIN ' . $publicDb . '.subjects s ON s.id = c.subject_id
            LEFT JOIN cover_cache cc ON cc.subject_id = c.subject_id AND cc.status = \'cached\'
            WHERE c.collected = TRUE AND s.type = 2
            ORDER BY c.collection_date DESC, c.updated_at DESC LIMIT :limit OFFSET :offset';
    $stmt = db_library()->prepare($sql);
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}
