-- Add homepage pagination indexes for existing chrono_bangumi databases.
-- Run after selecting the chrono_bangumi database. Safe to run repeatedly.

CREATE INDEX IF NOT EXISTS `idx_subjects_type_date_id`
ON `subjects` (`type`, `date`, `id`);

CREATE INDEX IF NOT EXISTS `idx_subjects_type_score_id`
ON `subjects` (`type`, `score`, `id`);
