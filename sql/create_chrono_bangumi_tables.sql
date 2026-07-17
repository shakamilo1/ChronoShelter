-- ChronoShelter public Bangumi Archive cache tables.
-- Target database: chrono_bangumi (select the database manually before executing).
-- This file contains CREATE TABLE statements only. It defines tables only and does not touch chrono_shelter.
-- Field names follow the official bangumi/Archive README model.

CREATE TABLE IF NOT EXISTS `subjects` (
  `id` INT UNSIGNED NOT NULL COMMENT 'Archive Subject.id',
  `type` TINYINT UNSIGNED NULL COMMENT 'Archive Subject.type: 1 book, 2 anime, 3 music, 4 game, 6 real',
  `name` VARCHAR(512) NULL,
  `name_cn` VARCHAR(512) NULL,
  `infobox` MEDIUMTEXT NULL COMMENT 'Archive Subject.infobox raw wiki string',
  `platform` SMALLINT UNSIGNED NULL COMMENT 'Archive Subject.platform',
  `summary` MEDIUMTEXT NULL,
  `nsfw` BOOLEAN NULL,
  `date` VARCHAR(32) NULL,
  `favorite` JSON NULL,
  `series` BOOLEAN NULL,
  `tags` JSON NULL,
  `score` FLOAT NULL,
  `score_details` JSON NULL,
  `rank` SMALLINT UNSIGNED NULL,
  `meta_tags` JSON NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `episodes` (
  `id` INT UNSIGNED NOT NULL COMMENT 'Archive Episode.id',
  `name` VARCHAR(512) NULL,
  `name_cn` VARCHAR(512) NULL,
  `description` MEDIUMTEXT NULL,
  `airdate` VARCHAR(32) NULL,
  `disc` SMALLINT UNSIGNED NULL,
  `duration` VARCHAR(64) NULL,
  `subject_id` INT UNSIGNED NOT NULL,
  `sort` FLOAT NULL,
  `type` TINYINT UNSIGNED NULL COMMENT 'Archive Episode.type: 0 main, 1 special, 2 OP, 3 ED, 4 trailer, 5 MAD, 6 other',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `persons` (
  `id` INT UNSIGNED NOT NULL COMMENT 'Archive Person.id',
  `name` VARCHAR(512) NULL,
  `type` TINYINT UNSIGNED NULL COMMENT 'Archive Person.type: 1 person, 2 company, 3 group',
  `career` JSON NULL,
  `infobox` MEDIUMTEXT NULL,
  `summary` MEDIUMTEXT NULL,
  `comments` INT UNSIGNED NULL,
  `collects` INT UNSIGNED NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `characters` (
  `id` INT UNSIGNED NOT NULL COMMENT 'Archive Character.id',
  `role` TINYINT UNSIGNED NULL COMMENT 'Archive Character.role',
  `name` VARCHAR(512) NULL,
  `infobox` MEDIUMTEXT NULL,
  `summary` MEDIUMTEXT NULL,
  `comments` INT UNSIGNED NULL,
  `collects` INT UNSIGNED NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_relations` (
  `subject_id` INT UNSIGNED NOT NULL,
  `relation_type` SMALLINT UNSIGNED NOT NULL,
  `related_subject_id` INT UNSIGNED NOT NULL,
  `order` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`subject_id`, `relation_type`, `related_subject_id`, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_characters` (
  `character_id` INT UNSIGNED NOT NULL,
  `subject_id` INT UNSIGNED NOT NULL,
  `type` TINYINT UNSIGNED NULL COMMENT 'Archive SubjectCharacter.type: 1 main, 2 supporting, 3 guest',
  `order` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`subject_id`, `character_id`, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_persons` (
  `person_id` INT UNSIGNED NOT NULL,
  `subject_id` INT UNSIGNED NOT NULL,
  `position` SMALLINT UNSIGNED NOT NULL COMMENT 'Archive SubjectPerson.position',
  `appear_eps` JSON NULL COMMENT 'Archive SubjectPerson.appear_eps, exported from 2025-09-29',
  PRIMARY KEY (`subject_id`, `person_id`, `position`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `person_characters` (
  `person_id` INT UNSIGNED NOT NULL,
  `subject_id` INT UNSIGNED NOT NULL,
  `character_id` INT UNSIGNED NOT NULL,
  `summary` TEXT NULL,
  PRIMARY KEY (`subject_id`, `person_id`, `character_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `person_relations` (
  `person_type` VARCHAR(16) NOT NULL COMMENT 'Archive PersonRelation.person_type: prsn or crt',
  `person_id` INT UNSIGNED NOT NULL,
  `related_person_id` INT UNSIGNED NOT NULL,
  `relation_type` VARCHAR(64) NOT NULL,
  `spoiler` BOOLEAN NULL,
  `ended` BOOLEAN NULL,
  PRIMARY KEY (`person_type`, `person_id`, `related_person_id`, `relation_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
