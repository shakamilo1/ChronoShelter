<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function list_anime(int $limit = 60, int $offset = 0): array
{
    $libraryDb = db_identifier(library_database_name());
    $sql = 'SELECT s.id, s.name, s.name_cn, s.date, s.score, s.favorite, cc.local_path AS cover_local_path, c.subject_id AS collected_subject_id
            FROM subjects s
            LEFT JOIN ' . $libraryDb . '.cover_cache cc ON cc.subject_id = s.id AND cc.status = \'cached\'
            LEFT JOIN ' . $libraryDb . '.collections c ON c.subject_id = s.id AND c.collected = TRUE
            WHERE s.type = 2
            ORDER BY COALESCE(s.score, 0) DESC, s.id DESC
            LIMIT :limit OFFSET :offset';
    $stmt = db_public()->prepare($sql);
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function count_anime(): int
{
    return (int) db_public()->query('SELECT COUNT(*) FROM subjects WHERE type = 2')->fetchColumn();
}

function get_subject(int $id): ?array
{
    $libraryDb = db_identifier(library_database_name());
    $sql = 'SELECT s.*, cc.local_path AS cover_local_path
            FROM subjects s
            LEFT JOIN ' . $libraryDb . '.cover_cache cc ON cc.subject_id = s.id AND cc.status = \'cached\'
            WHERE s.id = :id AND s.type = 2';
    $stmt = db_public()->prepare($sql);
    $stmt->execute(['id' => $id]);
    $subject = $stmt->fetch();
    return $subject ?: null;
}

function get_episodes_count(int $subjectId): int
{
    $stmt = db_public()->prepare('SELECT COUNT(*) FROM episodes WHERE subject_id = :id AND type = 0');
    $stmt->execute(['id' => $subjectId]);
    return (int) $stmt->fetchColumn();
}

function get_subject_persons(int $subjectId): array
{
    $sql = 'SELECT p.id, p.name, sp.position
            FROM subject_persons sp JOIN persons p ON p.id = sp.person_id
            WHERE sp.subject_id = :id ORDER BY sp.position, p.name LIMIT 80';
    $stmt = db_public()->prepare($sql);
    $stmt->execute(['id' => $subjectId]);
    return $stmt->fetchAll();
}

function get_subject_characters(int $subjectId): array
{
    $sql = 'SELECT c.id, c.name, sc.type
            FROM subject_characters sc JOIN characters c ON c.id = sc.character_id
            WHERE sc.subject_id = :id ORDER BY sc.type, sc.`order`, c.name LIMIT 80';
    $stmt = db_public()->prepare($sql);
    $stmt->execute(['id' => $subjectId]);
    return $stmt->fetchAll();
}

function decode_json_field(?string $json): array
{
    if ($json === null || $json === '') return [];
    $decoded = json_decode($json, true);
    return is_array($decoded) ? $decoded : [];
}

function subject_year(?string $date): string
{
    return $date && preg_match('/^(\d{4})/', $date, $m) ? $m[1] : '';
}

function subject_favorite_count(?string $favorite): string
{
    $data = decode_json_field($favorite);
    $sum = 0;
    foreach ($data as $value) {
        if (is_numeric($value)) $sum += (int) $value;
    }
    return $sum > 0 ? (string) $sum : '';
}

function subject_tags(?string $tags): array
{
    $data = decode_json_field($tags);
    $names = [];
    foreach ($data as $item) {
        if (is_array($item) && isset($item['name'])) $names[] = (string) $item['name'];
        elseif (is_string($item)) $names[] = $item;
    }
    return array_slice($names, 0, 30);
}
