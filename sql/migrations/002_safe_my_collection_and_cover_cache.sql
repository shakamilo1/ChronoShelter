-- Safe additive migration for ChronoShelter public library + personal collection.
-- Do NOT drop, truncate, or rebuild user tables.
-- Recommended before running: mysqldump --single-transaction <db> my_collection > backups/my_collection_before_002.sql

CREATE TABLE IF NOT EXISTS my_collection_legacy_backup AS SELECT * FROM my_collection;

CREATE TABLE IF NOT EXISTS my_collection (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  bangumi_id BIGINT NOT NULL,
  collected BOOLEAN NOT NULL DEFAULT TRUE,
  collection_date DATE NULL,
  media_type VARCHAR(128) NULL,
  subtitle_group VARCHAR(255) NULL,
  source_site VARCHAR(255) NULL,
  my_rating FLOAT NULL,
  notes TEXT NULL,
  extra_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_my_collection_bangumi_id (bangumi_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_local_path TEXT NULL AFTER image_large;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_cache_status VARCHAR(32) NULL AFTER cover_local_path;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_cached_at DATETIME NULL AFTER cover_cache_status;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS broadcast TEXT NULL AFTER raw_air_date;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS sites_json JSON NULL AFTER broadcast;
