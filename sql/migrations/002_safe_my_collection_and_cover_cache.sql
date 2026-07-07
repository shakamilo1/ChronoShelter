-- Safe additive migration for ChronoShelter public library + personal collection.
-- Do NOT drop, truncate, rebuild, or rename existing user tables.
-- Before running, inspect and dump first:
--   python tools/inspect_schema.py
--   mysqldump --single-transaction <db> my_collection > backups/my_collection_before_002.sql

-- If my_collection already exists, only nullable columns are added. Existing fields keep their meaning.
CREATE TABLE IF NOT EXISTS my_collection (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  bangumi_id BIGINT NOT NULL,
  collected BOOLEAN NULL,
  collection_date DATE NULL,
  media_type VARCHAR(128) NULL,
  subtitle_group VARCHAR(255) NULL,
  source_site VARCHAR(255) NULL,
  my_rating FLOAT NULL,
  notes TEXT NULL,
  extra_json JSON NULL,
  created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_my_collection_bangumi_id (bangumi_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS bangumi_id BIGINT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS collected BOOLEAN NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS collection_date DATE NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS media_type VARCHAR(128) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS subtitle_group VARCHAR(255) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS source_site VARCHAR(255) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS my_rating FLOAT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS notes TEXT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS extra_json JSON NULL;

ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_local_path TEXT NULL AFTER image_large;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_cache_status VARCHAR(32) NULL AFTER cover_local_path;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_cached_at DATETIME NULL AFTER cover_cache_status;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS broadcast TEXT NULL AFTER raw_air_date;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS sites_json JSON NULL AFTER broadcast;
