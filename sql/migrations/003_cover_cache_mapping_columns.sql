-- Add explicit cover mapping fields used by the Bangumi type=2 offline cover synchronizer.
-- Safe to run more than once on MySQL 8.0+ / MariaDB versions that support IF NOT EXISTS.

ALTER TABLE `cover_cache`
  ADD COLUMN IF NOT EXISTS `remote_filename` VARCHAR(255) NULL COMMENT 'Safe basename from Bangumi images.large URL, e.g. 1234_Ewjo.jpg' AFTER `status`,
  ADD COLUMN IF NOT EXISTS `source_url` VARCHAR(1024) NULL COMMENT 'Original Bangumi images.large URL for the cached local file' AFTER `remote_filename`,
  MODIFY COLUMN `local_path` VARCHAR(512) NULL COMMENT 'subjects/{level1}/{level2}/{subject_id}_{BangumiSuffix}.{ext} relative to covers/ when cached',
  ADD COLUMN IF NOT EXISTS `sha256` CHAR(64) NULL AFTER `file_size`;
