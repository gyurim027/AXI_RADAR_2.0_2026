CREATE TABLE `jurisdiction` (
  `jurisdiction_id` VARCHAR(20) NOT NULL COMMENT '담당 부서 표 ID (JUR-01 …) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `problem` VARCHAR(200) NOT NULL COMMENT '문제 유형 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `mvp_scope` VARCHAR(10) COMMENT 'MVP 범위: MVP / 미정 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `related_dept` VARCHAR(300) COMMENT '유관 부서(협의·승인) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `handling_time` VARCHAR(50) COMMENT '처리 시점 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `basis` VARCHAR(500) COMMENT '근거(확인한 소스: 업무분장·사무위임 조례 등) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `confirm_status` VARCHAR(20) COMMENT '근거 확인 상태: 확인됨 / 확인 필요 / 근거 없음 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `note` VARCHAR(500) COMMENT '비고 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `linked_uc` VARCHAR(100) COMMENT '연결 업무 ID (UC-01 … 쉼표로) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `source` VARCHAR(200) COMMENT '어디서 옮겼는지(대장 판) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `setting_version_id` BIGINT NULL COMMENT '이 줄을 마지막으로 바꾼 승인 버전 — 62 setting_version (F-05 수정안이 승인되면 채움). 초기 적재는 비움 [MVP: 운영 입력]',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '마지막으로 바뀐 시각 — DB가 자동으로 채움(넣을 때·고칠 때) [MVP: 운영 입력]',
  PRIMARY KEY (`jurisdiction_id`),
  CONSTRAINT `fk_jurisdiction_1` FOREIGN KEY (`setting_version_id`) REFERENCES `setting_version` (`setting_version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='담당 부서 표 (F-05 · A-11·A-12) — 문제 유형 한 줄. 대장 v0.4.2 기준(05 관할 매핑 JUR-01~23), 대장 05가 바뀌면 다시 넣음. 1차 해결 부서는 88 jurisdiction_dept';
