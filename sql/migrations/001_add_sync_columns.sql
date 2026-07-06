-- Migration-safe additive changes only. Never drop, truncate, or rebuild existing tables.
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS cover_local_path TEXT NULL AFTER image_large;
ALTER TABLE bangumi_anime ADD COLUMN IF NOT EXISTS broadcast TEXT NULL AFTER cover_local_path;
