CREATE TABLE `app_user` (
  `user_id` BIGINT NOT NULL COMMENT '사용자 번호(PK) [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `login_id` VARCHAR(100) COMMENT '로그인 아이디 (겹치지 않음, UNIQUE) [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `password_hash` VARCHAR(255) COMMENT '비밀번호 해시값만 (원문 저장 금지) [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `display_name` VARCHAR(255) COMMENT '화면에 보일 이름 [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `org_name` VARCHAR(255) COMMENT '기관 (성남시 / ○○구청) [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `team_name` VARCHAR(255) COMMENT '팀 이름 [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `gu_name` VARCHAR(255) COMMENT '구 도로관리팀이면 담당 구(수정·중원·분당). 시 도로과·RADAR 운영자는 비움 [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `role` VARCHAR(255) COMMENT '역할 3개: 구 도로관리팀 · 시 도로과 · RADAR 운영자 (규림 기능정의서 v0.4.1) [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `is_active` VARCHAR(255) COMMENT '사용 중인 계정인지 [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  `failed_count` INT NOT NULL DEFAULT 0 COMMENT '연속으로 로그인을 틀린 횟수 — 틀릴 때마다 1 더함, 맞게 로그인하면 0으로 (I-01 로그인 잠금 · POL-022) [MVP: 운영 입력]',
  `locked_until` DATETIME NULL COMMENT '잠김이 풀리는 시각 — 연속 5번 틀리면 지금 + 10분, 잠기지 않았으면 NULL. 이 시각 전에는 비밀번호가 맞아도 로그인 막음 (I-01 · POL-022) [MVP: 운영 입력]',
  `created_at` DATETIME COMMENT '만든 시각 [MVP: (테이블 기준) 운영 입력 (지금은 빈 표)]',
  PRIMARY KEY (`user_id`),
  UNIQUE (`login_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='담당자 (역할 3개: 구 도로관리팀·시 도로과·RADAR 운영자) — v2.1 로그인 잠금(연속 5번 틀리면 10분, I-01 · POL-022)';
