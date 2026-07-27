<?php

declare(strict_types=1);

require_once __DIR__ . '/database.php';

function get_subject_episodes(int $subjectId): array
{
    $stmt = db_public()->prepare('SELECT * FROM episodes WHERE subject_id = :id AND type = 0 ORDER BY sort');
    $stmt->execute(['id' => $subjectId]);
    return $stmt->fetchAll();
}

function get_subject_relations(int $subjectId): array
{
    $stmt = db_public()->prepare('SELECT s.id, s.name, s.name_cn FROM subject_relations r JOIN subjects s ON s.id = r.related_subject_id WHERE r.subject_id = :id ORDER BY r.order');
    $stmt->execute(['id' => $subjectId]);
    return $stmt->fetchAll();
}

function subject_platform_name(?int $platform): string
{
    return match ($platform) {
        1 => 'TV',
        2 => 'OVA',
        3 => '剧场版',
        5 => 'WEB',
        default => '动画',
    };
}
