-- ChronoShelter personal library schema.
-- Target database: chrono_library
-- Do not store Bangumi public fields here. Public subject/person/episode data is read from chrono_bangumi.
-- This file does not touch the legacy chrono_shelter database.
-- Review and execute manually; the application/tools in this PR do not execute this SQL automatically.

CREATE DATABASE IF NOT EXISTS `chrono_library`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `chrono_library`;

CREATE TABLE IF NOT EXISTS `collections` (
  `subject_id` BIGINT UNSIGNED NOT NULL COMMENT 'References chrono_bangumi.subjects.id logically; no cross-database FK is declared',
  `collected` BOOLEAN NULL DEFAULT TRUE,
  `collection_date` DATE NULL,
  `media_type` VARCHAR(64) NULL,
  `subtitle_group` VARCHAR(255) NULL,
  `source_site` VARCHAR(255) NULL,
  `my_rating` TINYINT UNSIGNED NULL COMMENT 'Personal rating, normally 1-10',
  `notes` TEXT NULL,
  `watch_progress` VARCHAR(64) NULL,
  `extra_json` JSON NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`subject_id`),
  CONSTRAINT `chk_collections_my_rating` CHECK (`my_rating` IS NULL OR (`my_rating` >= 1 AND `my_rating` <= 10))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `cover_cache` (
  `subject_id` BIGINT UNSIGNED NOT NULL COMMENT 'Cover cache status for a Bangumi subject image',
  `status` VARCHAR(32) NOT NULL DEFAULT 'missing' COMMENT 'missing, cached, failed, invalid',
  `local_path` VARCHAR(512) NULL COMMENT 'media/covers/{subject_id}.jpg when cached',
  `error` TEXT NULL,
  `http_status` INT NULL,
  `content_type` VARCHAR(128) NULL,
  `file_size` BIGINT UNSIGNED NULL,
  `width` INT UNSIGNED NULL,
  `height` INT UNSIGNED NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`subject_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
