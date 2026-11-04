-- 71 alert_delivery: 실행 실패 말고 다른 알림(갱신 예정일 지남 · 규정 개정 · 승인 결과)도 남기고 읽음을 저장하려고 칸 3개 + 키 1개를 더한다.
-- 10/28 은경 (I-03, AD-00 종 아이콘). 공용 DB에서 한 번만 실행. 다음 통합 SQL(v2.4)에 같은 내용을 넣는다.
-- 이 SQL 전 DB에서도 서버는 그대로 켜진다 (실패 알림만 보임 — app/services/ops/repository.py가 옛 칸으로 다시 읽음).

ALTER TABLE `alert_delivery`
  ADD COLUMN `alert_kind` VARCHAR(20) NULL COMMENT '알림 종류: failure(실행 실패) · staleData(갱신 예정일 지남) · regulation(규정 개정) · approval(승인 결과). 비어 있고 job_run_id가 있으면 실행 실패 (I-03)' AFTER `job_run_id`,
  ADD COLUMN `ref_table` VARCHAR(50) NULL COMMENT '알림이 가리키는 표 (source_list · standard_change · setting_version) — ref_id와 짝' AFTER `alert_kind`,
  ADD COLUMN `ref_id` VARCHAR(150) NULL COMMENT '그 표의 번호 (갱신 예정일 알림은 자료 번호@예정일). 표마다 키가 달라 글자로 저장, FK 없음' AFTER `ref_table`,
  ADD UNIQUE KEY `uq_alert_delivery_ref` (`alert_kind`, `ref_table`, `ref_id`);

-- 확인용
-- SHOW COLUMNS FROM alert_delivery;   → alert_kind · ref_table · ref_id 가 보이면 끝
