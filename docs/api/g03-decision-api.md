# G-03 후보 결정 API — 현재 구현 명세

상태: **개발용 메모리 저장·조회 구현**. 운영 DB 저장 및 팀 공통 API 병합 전. 기준: `app/api/g03_decision_api.py`와 `app/services/g01_g06/g03_candidate_decision.py` (2026-10-29 확인).
서버: 공용 FastAPI 라우터로 등록될 경우 공용 서버의 주소를 사용하며, 포트는 본 모듈에 지정되어 있지 않음. `app/main.py` 등록은 통합 담당자 작업.
본문은 JSON, UTF-8. 외부 AI 호출 없음. `AI_G03_DEV_API_ENABLED=1` 및 `AI_G03_REASON_CODES` 설정이 필요함. **운영 DB 쓰기 없음**.
사용 화면: **US-03 ⑤ 후보 결정**. 프론트 `saveDecision` 요청 키와의 매핑은 아직 미연결.

## 1. 최초 후보 결정 저장

POST `/api/g03/runs/{run_id}/candidates/{gid}/decision`

경로: `run_id`는 양의 정수, `gid`는 공백이 아닌 격자 ID. 로그인 필요, 역할 `district` 및 자신에게 허용된 구의 후보만 처리.
요청 JSON: `decision`은 `우선 점검 대상` / `제외` / `보류`; `reason_code`는 등록된 공식 사유 코드(제외·보류 시 필수), `memo`는 최대 200자 문자열(선택).

요청 예시(사유 코드는 **가상 예시**이며 실제 허용 코드는 환경 설정에 따름):
```json
{"decision":"보류","reason_code":"SAMPLE_REASON","memo":"현장 확인 필요"}
```

201 성공 응답 구조 예시(가상 회차·후보·사용자 값):
```json
{"ok":true,"record":{"run_id":1,"gid":"SAMPLE-GID","gu":"분당구","decision":"보류","reason_code":"SAMPLE_REASON","memo":"현장 확인 필요","weight_version":"SAMPLE-RULE","actor_ref":"12","decided_at":"2026-10-29T00:00:00+00:00","storage":"development_store_only"},"storage":"development_memory_only","operational_saved":false}
```

현재는 최초 결정만 등록함. 동일한 `(run_id, gid)`의 기존 결정은 409로 거부; 변경은 G-04 범위. 후보 데이터는 `PriorityRepository`에서 조회하며, `priority_candidate.selected_yn`을 수정하지 않음. `weight_version`에는 현재 `priority_run.rule_version`을 사용하나 실제 가중치 버전과 일치한다는 검증은 미완료. 개발 경로는 회차 확정 여부를 검증하지 못하므로 운영 사용 금지.

## 2. 후보 결정 조회

GET `/api/g03/runs/{run_id}/candidates/{gid}/decision`

경로와 로그인·담당 구 제한은 최초 결정 API와 같음. 요청 본문 없음.

200 성공 응답 구조 예시:
```json
{"record":{"run_id":1,"gid":"SAMPLE-GID","gu":"분당구","decision":"보류","reason_code":"SAMPLE_REASON","memo":"현장 확인 필요","weight_version":"SAMPLE-RULE","actor_ref":"12","decided_at":"2026-10-29T00:00:00+00:00","storage":"development_store_only"},"storage":"development_memory_only","operational_saved":false}
```

기록이 없으면 404. 저장은 단일 서버 프로세스의 메모리에 한정되므로 재시작 시 소멸하며 복수 프로세스 간 동기화되지 않음.

## 3. 오류

| HTTP | 발생 조건 | 처리 |
|---|---|---|
| 400 | 지원하지 않는 결정값, 사유 코드 누락·불일치 등 도메인 검증 실패 | `detail`에 오류 메시지 반환 |
| 401 | 인증되지 않은 사용자 | 공용 `current_user` 인증 의존성 처리 |
| 403 | 개발 기능 비활성화, 구 도로관리팀 역할·담당 구·사용자 식별 불일치 | 접근 거부 |
| 404 | 회차·후보 또는 조회할 개발용 결정 기록 없음 | `detail`로 구분 |
| 409 | 이미 결정이 존재함, 회차 규칙 버전 미확인 | 최초 결정 저장 거부 |
| 422 | 요청 본문·경로의 형식 문제, 잘못된 회차/격자 값 | FastAPI 검증 또는 명시적 거부 |
| 503 | `AI_G03_REASON_CODES` 미설정 | 기능 사용 불가 |

위 API는 별도의 표준화된 `error` 코드 필드를 구현하지 않았으며 현재 FastAPI `detail` 응답을 사용함. DB 오류에 대한 전용 503 응답 계약도 현재 구현되어 있지 않음.

## 4. 다른 저장 방식과 구분

`app/services/g01_g06/g03_candidate_decision.py`의 `InMemoryDecisionStore` 기반 개발용 경로임. 운영용 DB 저장, 인증된 회차 확정 상태 확인, G-04 변경 이력 영속화는 연결되지 않음. `priority_candidate.selected_yn`은 산정 결과로, G-03 사람의 결정값이 아님. 현재 프론트 `saveDecision`의 `runId`, `reasonKey` 등과 이 API의 `run_id` 경로·`reason_code` 본문은 동일 계약으로 확인되지 않았음.

## 5. 팀 통합 협의

- 프론트 결정값·사유 코드 매핑, 특히 `기타` 사유와 변경 사유 계약 확정 필요.
- G-03 운영 결정의 영속 저장 위치 및 `(run_id, gid)` 연결, 권한·회차 확정 여부 확인 방식 협의 필요.
- 라우터: `app.api.g03_decision_api.router`, 기본 경로 `/api/g03`. 공용 `app/main.py`는 통합 담당자가 등록하며 기능 담당자는 직접 수정하지 않음.
- 현재 POST 201은 **개발용 메모리에만 저장 성공**을 뜻하며 운영 DB 저장 성공을 의미하지 않음.
