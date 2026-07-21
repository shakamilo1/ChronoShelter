-- ChronoShelter recommended indexes for chrono_library.
-- Import this file into the chrono_library database.

CREATE INDEX IF NOT EXISTS `idx_collections_collected` ON `collections` (`collected`);
CREATE INDEX IF NOT EXISTS `idx_collections_collection_date` ON `collections` (`collection_date`);
CREATE INDEX IF NOT EXISTS `idx_cover_cache_status` ON `cover_cache` (`status`);
CREATE INDEX IF NOT EXISTS `idx_cover_cache_updated_at` ON `cover_cache` (`updated_at`);
