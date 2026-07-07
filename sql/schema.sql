-- Public Bangumi Archive tables. These tables may be fully rebuilt from Archive releases.
CREATE TABLE IF NOT EXISTS subject (
  id BIGINT PRIMARY KEY,
  type INT NULL,
  name VARCHAR(512) NULL,
  name_cn VARCHAR(512) NULL,
  summary TEXT NULL,
  date DATE NULL,
  eps INT NULL,
  volumes INT NULL,
  score FLOAT NULL,
  rating_count INT NULL,
  rank INT NULL,
  images JSON NULL,
  tags JSON NULL,
  infobox JSON NULL,
  meta JSON NULL,
  raw_json JSON NULL,
  updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS episode (
  id BIGINT PRIMARY KEY,
  subject_id BIGINT NOT NULL,
  sort FLOAT NULL,
  type INT NULL,
  name VARCHAR(512) NULL,
  name_cn VARCHAR(512) NULL,
  duration VARCHAR(128) NULL,
  airdate DATE NULL,
  comment INT NULL,
  raw_json JSON NULL,
  INDEX idx_episode_subject (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS person (
  id BIGINT PRIMARY KEY,
  name VARCHAR(512) NULL,
  type INT NULL,
  summary TEXT NULL,
  raw_json JSON NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `character` (
  id BIGINT PRIMARY KEY,
  name VARCHAR(512) NULL,
  summary TEXT NULL,
  raw_json JSON NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subject_person (
  subject_id BIGINT NOT NULL,
  person_id BIGINT NOT NULL,
  relation VARCHAR(255) NULL,
  raw_json JSON NULL,
  PRIMARY KEY (subject_id, person_id, relation),
  INDEX idx_subject_person_person (person_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subject_character (
  subject_id BIGINT NOT NULL,
  character_id BIGINT NOT NULL,
  relation VARCHAR(255) NULL,
  raw_json JSON NULL,
  PRIMARY KEY (subject_id, character_id, relation),
  INDEX idx_subject_character_character (character_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subject_relation (
  subject_id BIGINT NOT NULL,
  related_subject_id BIGINT NOT NULL,
  relation VARCHAR(255) NULL,
  raw_json JSON NULL,
  PRIMARY KEY (subject_id, related_subject_id, relation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS person_character (
  person_id BIGINT NOT NULL,
  character_id BIGINT NOT NULL,
  subject_id BIGINT NULL,
  relation VARCHAR(255) NULL,
  raw_json JSON NULL,
  PRIMARY KEY (person_id, character_id, subject_id, relation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS person_relation (
  person_id BIGINT NOT NULL,
  related_person_id BIGINT NOT NULL,
  relation VARCHAR(255) NULL,
  raw_json JSON NULL,
  PRIMARY KEY (person_id, related_person_id, relation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Personal table. Never rebuild from Archive updates.
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
