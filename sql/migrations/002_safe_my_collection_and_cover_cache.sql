-- Safe additive personal collection migration for Archive-based ChronoShelter.
-- Do NOT drop, truncate, rebuild, or rename existing my_collection.
-- Before running:
--   python tools/inspect_schema.py
--   mysqldump --single-transaction <db> my_collection > backups/my_collection_before_archive.sql

CREATE TABLE IF NOT EXISTS my_collection (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  subject_id BIGINT NULL,
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
  UNIQUE KEY uk_my_collection_subject_id (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS subject_id BIGINT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS collected BOOLEAN NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS collection_date DATE NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS media_type VARCHAR(128) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS subtitle_group VARCHAR(255) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS source_site VARCHAR(255) NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS my_rating FLOAT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS notes TEXT NULL;
ALTER TABLE my_collection ADD COLUMN IF NOT EXISTS extra_json JSON NULL;
