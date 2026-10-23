# AI-07 DB 읽기 전용 API — 현재 구현 명세

상태: PC 내부 개발·연결 시험용 구현. 팀 공통 API 확정/병합 전. 작성 2026-10-20, GitHub 제출 경로 정리 2026-10-21.
서버: http://127.0.0.1:8007. 기존 별도 데모 프론트에서는 Vite 프록시로 시험했다. 이번 제출에는 프론트 변경이 없으며 팀 화면 연결은 별도 작업이다.
본문은 JSON, UTF-8. 이 모드는 GET 전용이며 외부 LLM 호출/결과 저장 기능이 없다.

## 1. 실행 목록
GET /api/ai07/db/runs
쿼리 매개변수 없음.
200 공통 필드: schema_version="ai07.db-readonly.v1", data_origin="server_db", read_only=true, external_api_called=false.
추가 필드: status="ok" 또는 "no_results", runs=[...], truncated=boolean.
run 각 항목: run_id(string), build_id(string|null), rule_version(string|null), created_at(string|null).
최신 실행 번호 내림차순 최대 20건. 다음 페이지 API는 없고 초과 여부만 표시한다.

빈 DB 응답 예:
```json
{"schema_version":"ai07.db-readonly.v1","data_origin":"server_db","read_only":true,"external_api_called":false,"status":"no_results","runs":[],"truncated":false}
```

## 2. 실행별 후보 목록
GET /api/ai07/db/candidates?run_id=900001
run_id: 숫자로만 된 1~19자 문자열, signed BIGINT 최댓값 이하. 0도 현재 구현상 허용하며 존재하지 않으면 빈 목록을 반환한다.
200: 공통 필드 + run_id(string), status="ok"|"no_results", candidates=[...], truncated=boolean.
각 후보: run_id(string), gid(string), selected_yn(string|null), score(소수 문자열|null), rank_no(integer|null).
NULL 순위 뒤로, 저장 순위와 gid 순으로 최대 100건. 후보 선정 Y/N을 모두 반환한다. 표시 순서로 새 순위를 계산하지 않는다. 101건 이상은 잘림 표시하며 현재 페이지 이동은 지원하지 않는다.

## 3. 후보 설명
GET /api/ai07/db/explanation?run_id=900001&gid=SYNTHETIC-GRID-A
run_id 위와 동일. gid는 1~32자, 비ASCII 문자는 URL 인코딩한다.
조회 키는 (run_id, gid) 쌍이다. gid 하나만으로 다른 실행의 결과를 연결하지 않는다.
200 찾음: 공통 필드 + run_id, gid, status="ok", candidate, explanation(string), generation_method="local_template".
candidate: 목록의 5칸 + build_id, rule_version, created_at.
200 점수/순위 NULL: status="missing_values", explanation=null, candidate와 generation_method 포함.
200 없음: status="not_found", explanation=null. 이 경우 candidate와 generation_method는 없다.
설명은 저장 점수·순위·규칙 버전의 요약이다. 전체 대상 수, 항목별 기여, 민원 반영 상태, 지표 출처·기준일, 승인 여부는 이 조회로 받지 않으므로 추정하지 않는다.

## 4. 오류
| HTTP | error | 처리 |
|---|---|---|
| 400 | invalid_input_or_stored_value | 잘못된 입력 또는 저장 점수·순위 값 보류 |
| 403 | local_access_only | 허용한 로컬 Host/Origin 조건 위반 |
| 404 | not_found | 미지원 경로/쿼리 구성 |
| 405 | read_only_get_only | POST 요청 거부 |
| 503 | db_read_failed | DB 조회 실패; 상세·비밀번호·SQL·행 내용을 응답/로그에 노출하지 않음 |

숫자는 SQL 바인딩으로 전달한다. 점수는 문자열로 소수 표기를 유지하고 실행 번호도 문자열로 보존한다. 0점과 NULL은 구분한다. 화면은 응답 실행/격자/점수/순위를 선택값과 대조하고 불일치·실패 시 설명을 표시하지 않는다. 가상 모드의 기본 문장 대체와 DB 모드의 조회 실패 처리는 서로 다르다.

## 5. 다른 실행 모드와 구분
backend/ai07/server.py의 POST /api/ai07/explain은 별도 가상 프론트 연결용이다. db_server.py는 이 POST를 제공하지 않고 405로 거부한다. 두 서버를 같은 8007 포트에 동시에 켜지 않는다.
현재 DB 모드에는 사용자 인증·구별 접근 권한이 없으므로 외부 공개 운영 서버로 배포하지 않는다.

## 6. 팀 통합 협의
계산 실행 당시의 근거 전달 형식, 최신 결과 제공 시점, 설명문 저장 위치, 인증·권한, 공통 오류/응답 형식을 합의해야 한다. priority_candidate_action.basis_text는 조치 제안 근거이므로 AI-07 점수 설명 저장 칸으로 임의 사용하지 않는다. 최신 grid_feature를 무조건 결합하면 실행 당시 근거와 다를 수 있다.
