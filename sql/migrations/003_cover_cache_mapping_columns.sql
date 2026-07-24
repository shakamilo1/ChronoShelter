-- Keep cover_cache focused on the website's current cover mapping.
-- This is idempotent and only helps early PR testers who created an earlier draft table.
ALTER TABLE `cover_cache`
  ADD COLUMN IF NOT EXISTS `remote_filename` VARCHAR(255) NULL COMMENT 'Safe basename from current Bangumi images.large URL, e.g. 1234_Ewjo.jpg' AFTER `status`,
  DROP COLUMN IF EXISTS `source_url`,
  DROP COLUMN IF EXISTS `error`,
  DROP COLUMN IF EXISTS `http_status`,
  DROP COLUMN IF EXISTS `content_type`,
  DROP COLUMN IF EXISTS `file_size`,
  DROP COLUMN IF EXISTS `sha256`,
  DROP COLUMN IF EXISTS `width`,
  DROP COLUMN IF EXISTS `height`;
