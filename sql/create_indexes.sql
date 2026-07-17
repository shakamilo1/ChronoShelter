-- ChronoShelter recommended indexes for chrono_bangumi and chrono_library.
-- Review and execute manually after creating/importing tables. This file does not touch chrono_shelter.

USE `chrono_bangumi`;

CREATE INDEX IF NOT EXISTS `idx_subjects_type` ON `subjects` (`type`);
CREATE INDEX IF NOT EXISTS `idx_subjects_name` ON `subjects` (`name`);
CREATE INDEX IF NOT EXISTS `idx_subjects_name_cn` ON `subjects` (`name_cn`);
CREATE INDEX IF NOT EXISTS `idx_subjects_type_date` ON `subjects` (`type`, `date`);
CREATE INDEX IF NOT EXISTS `idx_subjects_rank` ON `subjects` (`rank`);

CREATE INDEX IF NOT EXISTS `idx_episodes_subject_id` ON `episodes` (`subject_id`);
CREATE INDEX IF NOT EXISTS `idx_episodes_subject_type_sort` ON `episodes` (`subject_id`, `type`, `sort`);

CREATE INDEX IF NOT EXISTS `idx_persons_name` ON `persons` (`name`);
CREATE INDEX IF NOT EXISTS `idx_characters_name` ON `characters` (`name`);

CREATE INDEX IF NOT EXISTS `idx_subject_persons_subject_id` ON `subject_persons` (`subject_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_persons_person_id` ON `subject_persons` (`person_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_persons_position` ON `subject_persons` (`position`);

CREATE INDEX IF NOT EXISTS `idx_subject_characters_subject_id` ON `subject_characters` (`subject_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_characters_character_id` ON `subject_characters` (`character_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_characters_type_order` ON `subject_characters` (`subject_id`, `type`, `order`);

CREATE INDEX IF NOT EXISTS `idx_subject_relations_subject_id` ON `subject_relations` (`subject_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_relations_related_subject_id` ON `subject_relations` (`related_subject_id`);
CREATE INDEX IF NOT EXISTS `idx_subject_relations_relation_type` ON `subject_relations` (`relation_type`);

CREATE INDEX IF NOT EXISTS `idx_person_characters_subject_id` ON `person_characters` (`subject_id`);
CREATE INDEX IF NOT EXISTS `idx_person_characters_person_id` ON `person_characters` (`person_id`);
CREATE INDEX IF NOT EXISTS `idx_person_characters_character_id` ON `person_characters` (`character_id`);

CREATE INDEX IF NOT EXISTS `idx_person_relations_person` ON `person_relations` (`person_type`, `person_id`);
CREATE INDEX IF NOT EXISTS `idx_person_relations_related_person_id` ON `person_relations` (`related_person_id`);
CREATE INDEX IF NOT EXISTS `idx_person_relations_relation_type` ON `person_relations` (`relation_type`);

USE `chrono_library`;

CREATE INDEX IF NOT EXISTS `idx_collections_collected` ON `collections` (`collected`);
CREATE INDEX IF NOT EXISTS `idx_collections_collection_date` ON `collections` (`collection_date`);
CREATE INDEX IF NOT EXISTS `idx_cover_cache_status` ON `cover_cache` (`status`);
CREATE INDEX IF NOT EXISTS `idx_cover_cache_updated_at` ON `cover_cache` (`updated_at`);
