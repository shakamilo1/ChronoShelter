-- ChronoShelter personal library tables.
-- Target database: chrono_library (select the database manually before executing).
-- This file contains CREATE TABLE statements only. It defines tables only and does not touch chrono_shelter.
-- Do not store Bangumi public fields here. Public subject/person/episode data is read from chrono_bangumi.

CREATE TABLE IF NOT EXISTS `collections` (
  `subject_id` INT UNSIGNED NOT NULL COMMENT 'Logical reference to chrono_bangumi.subjects.id; no cross-database FK is declared',
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
  `subject_id` INT UNSIGNED NOT NULL COMMENT 'Bangumi subject id for the current cover mapping',
  `status` VARCHAR(32) NOT NULL DEFAULT 'missing' COMMENT 'Current web mapping status: missing, cached, no_cover',
  `remote_filename` VARCHAR(255) NULL COMMENT 'Safe basename from current Bangumi images.large URL, e.g. 1234_Ewjo.jpg',
  `local_path` VARCHAR(512) NULL COMMENT 'subjects/{level1}/{level2}/{subject_id}_{BangumiSuffix}.{ext} relative to covers/ when cached',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`subject_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
