CREATE TABLE `access_audit` (
  `access_audit_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '접근 기록 번호 — DB가 자동으로 붙임 [MVP: 운영 입력]',
  `actor_ref` BIGINT COMMENT '누가 — 접속한 계정(app_user.user_id). 고시 제2조제3호 식별자 [MVP: 운영 입력]',
  `resource_kind` VARCHAR(255) COMMENT '무엇을 — 예: 민원 점 위치 · 파일 내려받기. 고시 제2조제3호 수행업무 [MVP: 운영 입력]',
  `resource_key` VARCHAR(255) COMMENT '어디를 — 민원 점 위치면 본 구(수정구·중원구·분당구), 파일이면 파일 이름. 고시 제2조제3호 처리한 정보주체 정보 [MVP: 운영 입력]',
  `accessed_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '언제 — 넣는 순간 DB가 지금 시각으로 채움. 고시 제2조제3호 접속일시 [MVP: 운영 입력]',
  `client_ip` VARCHAR(45) COMMENT '어디서 — 접속한 IP 주소(IPv6까지 45자). 고시 제2조제3호 접속지 정보 [MVP: 운영 입력]',
  `access_reason` VARCHAR(255) COMMENT '업무 목적 — 켠 화면 기준으로 시스템이 자동 입력(점검 후보 지도 = 점검 후보 검토, 검사 결과 화면 = 위치 품질 확인). 같은 구라도 화면이 바뀌어 목적이 달라지면 새 줄. 고시 제2조제3호 수행업무 [MVP: 운영 입력]',
  PRIMARY KEY (`access_audit_id`),
  CONSTRAINT `fk_access_audit_1` FOREIGN KEY (`actor_ref`) REFERENCES `app_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='접근 기록 (POL-022) — 민원 점 위치는 로그인 한 번 동안 구마다 한 줄: 그 구의 구역(격자)을 처음 누를 때 남김. 같은 구의 다른 구역·말풍선은 남기지 않음, 다시 로그인하면 처음부터. 백엔드가 자동으로 남김. 2년 이상 보관(고시 제8조①), 추가만 하고 수정·삭제 안 함(제8조③)';
