-- RADAR 2.0 SQL 추가 제안 · 91 app_setting (운영 설정 한 줄씩) · MySQL 8 · 2026-10-26 은경
-- 쓰는 곳: I-03 실패 알림 받을 메일 (화면명세 AD-17 '설정 > 알림 설정'), setting_key = 'alert_emails'
-- 기존 표·행은 건드리지 않는다 (추가만). 이미 있으면 그대로 둔다.
CREATE TABLE IF NOT EXISTS `app_setting` (
  `setting_key` VARCHAR(50) NOT NULL COMMENT '설정 이름 (예: alert_emails = 실패 알림 받을 메일, I-03 · AD-17)',
  `setting_value` VARCHAR(1000) NULL COMMENT '설정 값 (alert_emails는 쉼표로 이은 메일 주소)',
  `updated_by` BIGINT NULL COMMENT '마지막으로 바꾼 RADAR 운영자 — 60 app_user',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '마지막으로 바꾼 시각 — DB가 자동으로 채움',
  PRIMARY KEY (`setting_key`),
  CONSTRAINT `fk_app_setting_1` FOREIGN KEY (`updated_by`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='운영 설정 — 한 설정에 한 줄 (I-03 알림 메일 등). 바꾼 기록은 70 access_audit 설정 변경';
