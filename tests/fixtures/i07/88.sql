CREATE TABLE `jurisdiction_dept` (
  `jurisdiction_dept_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '1차 해결 부서 줄 번호 — 자동 번호 [MVP: 지금 가능]',
  `jurisdiction_id` VARCHAR(20) NOT NULL COMMENT '담당 부서 표 ID — 87 jurisdiction (JUR-01 …) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `sort_no` INT COMMENT '같은 유형 안 순서 — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `gu_name` VARCHAR(20) NULL COMMENT '구: 수정구 · 중원구 · 분당구 (시 부서이거나 모르면 NULL) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `condition_text` VARCHAR(100) NULL COMMENT '부서가 나뉘는 조건 (예: 국도3호선·국지도57·23호선, 보도 신설·확장). 없으면 NULL — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `dept_name` VARCHAR(200) NULL COMMENT '1차 해결 부서·팀 (근거 없음이면 NULL) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  `org_level` VARCHAR(10) NULL COMMENT '시 / 구 (모르면 NULL) — 대장 v0.4.2 기준 [MVP: 지금 가능]',
  PRIMARY KEY (`jurisdiction_dept_id`),
  CONSTRAINT `fk_jurisdiction_dept_1` FOREIGN KEY (`jurisdiction_id`) REFERENCES `jurisdiction` (`jurisdiction_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='1차 해결 부서 (F-05) — 87 담당 부서 표 한 유형에 부서마다 한 줄. 대장 v0.4.2 기준, 대장 05가 바뀌면 87과 같이 다시 넣음';
