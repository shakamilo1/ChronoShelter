-- ChronoShelter public Bangumi Archive cache schema.
-- Target database: chrono_bangumi
-- This file only defines the new public cache database. It does not touch the legacy chrono_shelter database.
-- Review and execute manually; the application/tools in this PR do not execute this SQL automatically.

CREATE DATABASE IF NOT EXISTS `chrono_bangumi`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `chrono_bangumi`;

CREATE TABLE IF NOT EXISTS `subjects` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT 'Archive subject id',
  `type` TINYINT UNSIGNED NULL COMMENT '1=book, 2=anime, 3=music, 4=game, 6=real',
  `name` VARCHAR(512) NULL,
  `name_cn` VARCHAR(512) NULL,
  `infobox` MEDIUMTEXT NULL COMMENT 'Raw Bangumi wiki infobox string',
  `platform` VARCHAR(128) NULL,
  `summary` MEDIUMTEXT NULL,
  `tags` JSON NULL,
  `meta_tags` JSON NULL,
  `score` FLOAT NULL,
  `score_details` JSON NULL,
  `rank` INT NULL,
  `favorite` JSON NULL COMMENT 'Bangumi public favorite counters',
  `date` VARCHAR(32) NULL COMMENT 'Archive release/air date string',
  `nsfw` BOOLEAN NULL,
  `series` BOOLEAN NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `episodes` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT 'Archive episode id',
  `name` VARCHAR(512) NULL,
  `name_cn` VARCHAR(512) NULL,
  `description` MEDIUMTEXT NULL,
  `airdate` VARCHAR(32) NULL,
  `disc` INT NULL,
  `duration` VARCHAR(64) NULL,
  `subject_id` BIGINT UNSIGNED NOT NULL,
  `sort` FLOAT NULL,
  `type` TINYINT UNSIGNED NULL COMMENT '0=main, 1=special, 2=OP, 3=ED, 4=Trailer, 5=MAD, 6=other',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `persons` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT 'Archive person id',
  `name` VARCHAR(512) NULL,
  `type` TINYINT UNSIGNED NULL COMMENT '1=person, 2=company, 3=group',
  `career` JSON NULL,
  `infobox` MEDIUMTEXT NULL,
  `summary` MEDIUMTEXT NULL,
  `comments` INT NULL,
  `collects` INT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `characters` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT 'Archive character id',
  `role` TINYINT UNSIGNED NULL,
  `name` VARCHAR(512) NULL,
  `infobox` MEDIUMTEXT NULL,
  `summary` MEDIUMTEXT NULL,
  `comments` INT NULL,
  `collects` INT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_persons` (
  `subject_id` BIGINT UNSIGNED NOT NULL,
  `person_id` BIGINT UNSIGNED NOT NULL,
  `position` VARCHAR(128) NOT NULL,
  `appear_eps` JSON NULL COMMENT 'Archive exports this field for newer dumps; may be absent in older dumps',
  PRIMARY KEY (`subject_id`, `person_id`, `position`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_characters` (
  `subject_id` BIGINT UNSIGNED NOT NULL,
  `character_id` BIGINT UNSIGNED NOT NULL,
  `type` TINYINT UNSIGNED NULL COMMENT '1=main, 2=supporting, 3=guest',
  `order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`subject_id`, `character_id`, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `subject_relations` (
  `subject_id` BIGINT UNSIGNED NOT NULL,
  `relation_type` VARCHAR(64) NOT NULL,
  `related_subject_id` BIGINT UNSIGNED NOT NULL,
  `order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`subject_id`, `relation_type`, `related_subject_id`, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `person_characters` (
  `subject_id` BIGINT UNSIGNED NOT NULL,
  `person_id` BIGINT UNSIGNED NOT NULL,
  `character_id` BIGINT UNSIGNED NOT NULL,
  `summary` TEXT NULL,
  PRIMARY KEY (`subject_id`, `person_id`, `character_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `person_relations` (
  `person_type` VARCHAR(16) NOT NULL COMMENT 'prsn or crt',
  `person_id` BIGINT UNSIGNED NOT NULL,
  `related_person_id` BIGINT UNSIGNED NOT NULL,
  `relation_type` VARCHAR(64) NOT NULL,
  `spoiler` BOOLEAN NULL,
  `ended` BOOLEAN NULL,
  PRIMARY KEY (`person_type`, `person_id`, `related_person_id`, `relation_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
