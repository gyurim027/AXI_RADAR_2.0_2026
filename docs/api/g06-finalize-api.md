# G-06 구별 확정 API — 개발용 명세

기준: `app/api/g06_finalize_api.py`, `app/services/G-01~06/g06_round_finalize.py`, `app/services/priority/repository.py`, `app/core/auth.py`.
화면: **US-01 확정 영역, US-04 구별 확정 현황**. 본 API는 개발용 메모리 상태만 저장하며 운영 DB 변경이 없습니다.

## 1. 구별 확정 전 요약

- **GET** `/api/g06/runs/{run_id}/districts/me/confirmation`
- 경로값: `run_id` 양의 정수. 인증: 분당구·수정구·중원구 도로관리팀(`district`)의 자기 구만.
- 성공: **200**. 예시값은 가상이며 실제 DB 수치를 뜻하지 않음.

```json
{"role":"district","gu":"분당구","counts":{"target":2,"exclude":1,"hold":1,"none":3},"summary":{"run_id":1,"gu":"분당구","total_candidates":7,"selected_count":2,"excluded_count":1,"held_count":1,"undecided_count":3,"undecided_gids":["GRID-A","GRID-B","GRID-C"],"requires_reconfirmation":true},"mine":{"gu":"분당구","done":false,"date":null},"storage":"development_memory_only","operational_saved":false}
```

## 2. 구별 확정

- **POST** `/api/g06/runs/{run_id}/districts/me/confirmation`
- 본문: `explicitly_confirmed` 필수 불리언, `reconfirm_undecided` 선택 불리언(기본 `false`). 미결정 후보가 있으면 `true`로 재확인해야 함.

```json
{"explicitly_confirmed":true,"reconfirm_undecided":true}
```

- 성공: **201** 예시(가상값):

```json
{"ok":true,"result":{"run_id":1,"gu":"분당구","district_finalized":true,"finalized_districts":["분당구"],"round_finalized":false,"calculation_conditions_record":"연결 대기 / 실제 기록서 미생성","storage":"개발용 메모리 / 운영 DB 미저장"},"storage":"development_memory_only","operational_saved":false}
```

## 3. 구별·회차 확정 현황

- **GET** `/api/g06/runs/{run_id}/confirmation-status`
- `district`: 자기 구 상태만, `city`·`operator`: 3개 구 상태 조회.
- 성공: **200** (가상 예시):

```json
{"run_id":1,"guStatuses":[{"gu":"분당구","done":true},{"gu":"수정구","done":false},{"gu":"중원구","done":false}],"round_finalized":false,"storage":"development_memory_only","operational_saved":false}
```

## 4. 오류 코드

| HTTP | 조건 |
|---|---|
| 401 | 로그인 토큰 없음·만료·무효 (공통 인증) |
| 403 | 비활성화된 개발 API, 역할 불일치 |
| 404 | 회차 없음 |
| 409 | 중복 확정, 명시적 확정 누락, 미결정 재확인 누락, 산정 후보 없음 또는 개발 도메인 검증 오류 |
| 422 | 잘못된 회차/JSON 형식 |
| 503 | G-03 개발용 결정 API 비활성화 |

## 5. 연결·제약

- 활성화: 백엔드 `AI_G06_DEV_API_ENABLED=1` 및 `AI_G03_DEV_API_ENABLED=1` 필요.
- 후보 조회: 기존 `PriorityRepository.list_candidates()` 및 `grid_feature.id_gu` 관할 기준, 점수가 있는 후보(`score IS NOT NULL`)만 G-06 확정 요약에 포함. `grid_cell.gu_center`와 같은지 별도 확인 필요.
- 결정 조회: `app.api.g03_decision_api`의 **동일 프로세스 메모리 저장소**에 있는 G-03 기록만 사용. 이미 DB에 있는 후보라도 G-03 메모리 결정이 없으면 미결정 처리. 다중 프로세스 및 서버 재시작 불가.
- **중요 미연결**: 기존 G-03 POST가 G-06 확정 상태를 확인하지 않으므로 확정 후 G-03 추가 저장을 차단하지 못함. G-04 변경 제한, 실제 회차의 `검토 중` 상태, 운영 DB 확정, 산정 조건 기록서, 접근 기록은 미연결. 개발용으로만 사용.
- 프론트 `getConfirmSummary()`·`confirmGu()`는 현재 mockCall이며, 요청/응답 매핑은 아직 미연결. 특히 POST 결과를 프론트 `confirmOf` 형식으로 변환해야 함.
- `app/main.py`는 수정하지 않음. PR 등록 코드: `("G-06", "app.api.g06_finalize_api"),`
- DB 스키마 변경 없음. SQL·CSV 변경 자료 불필요.
