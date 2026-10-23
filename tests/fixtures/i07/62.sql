CREATE TABLE `setting_version` (
  `setting_version_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '설정 버전 번호 — DB가 자동으로 매김(v2.1부터 AUTO_INCREMENT) [MVP: 운영 입력]',
  `setting_kind` VARCHAR(255) COMMENT '설정 종류 (가중치 · 기준값 · 우선 확인 조건 · 담당 부서 표 — 담당 부서 표는 87 jurisdiction · 88 jurisdiction_dept) [MVP: 운영 입력]',
  `version_label` VARCHAR(255) COMMENT '버전 이름 [MVP: 운영 입력]',
  `content_ref` VARCHAR(255) COMMENT '설정 내용 또는 파일 위치 [MVP: 운영 입력]',
  `proposed_by` BIGINT COMMENT '제안한 사람(RADAR 운영자) [MVP: 운영 입력]',
  `proposed_at` DATETIME COMMENT '제안 시각 [MVP: 운영 입력]',
  `approval_status` VARCHAR(255) COMMENT '상태 (제안 · 승인 · 돌려보냄) [MVP: 운영 입력]',
  `approved_by` BIGINT COMMENT '승인·돌려보낸 사람(시 도로과) [MVP: 운영 입력]',
  `approved_at` DATETIME COMMENT '승인·돌려보낸 시각 [MVP: 운영 입력]',
  `review_comment` VARCHAR(255) COMMENT '돌려보낸 이유·의견 [MVP: 운영 입력]',
  PRIMARY KEY (`setting_version_id`),
  CONSTRAINT `fk_setting_version_1` FOREIGN KEY (`proposed_by`) REFERENCES `app_user` (`user_id`),
  CONSTRAINT `fk_setting_version_2` FOREIGN KEY (`approved_by`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='설정 버전 (제안·승인)';
