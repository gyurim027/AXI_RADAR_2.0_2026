# 보행안전 점검 우선순위 산정·분석 기능 — 격리 통합

기준: PR #7 6af10e9, core 3bd8929, llm f18eaf3. develop 병합·원격 최신 확인 아님.

## 실행
팀 저장소 루트, Python 3.11~3.13. 기존 의존성 외 pandas/numpy 필요(기존 ai03 선택 묶음에 있음). 공통 의존성 파일은 변경하지 않았다.

```powershell
python -m app.services.scoring.runtime execute --grid "입력경로/05_grid_feature.csv" --complaints "입력경로/민원탐색집계.csv" --config docs/scoring/independent.json --database "작업경로/scoring.sqlite"
python -m app.services.scoring.runtime execute --grid "입력경로/05_grid_feature.csv" --complaints "입력경로/민원탐색집계.csv" --config docs/scoring/inside_hazard.json --database "작업경로/scoring.sqlite"
python -m app.services.scoring.runtime execute --grid "입력경로/05_grid_feature.csv" --complaints "입력경로/민원탐색집계.csv" --config docs/scoring/bonus.json --database "작업경로/scoring.sqlite"
python -m app.services.scoring.runtime read --database "작업경로/scoring.sqlite" --run 920001 --gid "조회할격자"
python -m app.services.scoring.analysis --database "작업경로/scoring.sqlite" --runs 920001 920002 920003 --out "작업경로/analysis"
python -m pytest -q tests/test_scoring_runtime.py
node --test frontend/tests/scoring-client.test.mjs
```
입력경로는 실제 파일로 대체한다. 원자료는 코드 패치에 포함하지 않았다. 원본 05의 9개 지표·ID_gid·id_gu·ext_survey_scope_obstacle, 집계의 gid/complaint_all/complaint_lowexcluded/complaint_illustrative_filter를 사용한다. 기존 점수 CSV는 필요 없다. 입력 단위·기간의 원자료 의미 적격성은 아직 자동 검증 완료가 아니며 period_note는 기록용이다.

## 계산 및 저장
기존 calculation.py를 이동 재사용했다. 원자료에서 기본점수를 재계산하고 원래 연산 순서로 민원을 결합한다. 각 실험 설정은 계수 5점, 전체 입력 양수 모집단 정규화, hazard 관측 모집단 비교이다. 공식 정책이 아니다. 지표 기여점은 **민원 결합 전 기본점수의 기여점**이다. 최종 총점은 기본점수+민원 점수항+기본점수 조정+상한조정+반올림조정으로 분해한다. 기본 지표 기여 합에는 기본점수 반올림 오차가 있을 수 있다.

기존 격리 62/77/78/setting_snapshot/evidence 스키마를 재사용했다. 입력 파일 바이트를 한 번 읽어 해시와 계산에 같이 사용한다. manifest를 기존 evidence payload에 저장한다. BEGIN IMMEDIATE와 단일 트랜잭션으로 부분 실패를 되돌린다. 같은 회차·같은 실행 지문은 저장값 검증 후 재사용, 다른 지문은 거부한다. 동일 설정 ID 재사용은 현재 보수적으로 거부한다. 운영 회차 생성·검토 상태 관리 기능은 구현하지 않았다.

content_ref는 격리 실행에서 isolated-config-sha256: 접두어로 명시한다. 팀의 기존 content_ref를 JSON/경로로 임의 해석하지 않는다. **실제 62 설정 로더 계약과 운영 MySQL 저장 연결은 미완료**이다. 승인 변경은 기존 스냅샷과의 불일치로 조회 차단되며 공식화되지 않는다. 해시와 DB를 동시에 고치는 공격까지 보장하는 서명·불변 저장은 아니다.

## API·화면 최소 연결 위치
공통 main.py와 후보 페이지는 변경하지 않았다. 격리 FastAPI 앱 또는 검토용 main 등록 위치:

```python
from app.services.scoring.api import create_router
app.include_router(create_router(ISOLATED_DATABASE_PATH))
```
기존 CamelCaseMiddleware·install_error_handlers·current_user를 사용한다. GET /api/scoring-result/runs/{run_id}/candidates/{gid}. 서버 경로는 명시적으로 주입하며 운영 환경에서 자동 활성화하지 않는다. 원시 SQL/예외 상세는 API 오류에 노출하지 않는다.

후보 상세 패널 적용 위치: frontend/src/api/scoring/ScoringEvidence.jsx. runId, gid, 안정적인 authenticated fetcher를 주입한다. fetcher는 팀 인증 토큰을 포함해 Response를 반환해야 한다. candidates.js의 후보선정·담당부서 변경 호출은 대체하지 않는다. 실제 후보 페이지 장착·브라우저 확인은 미완료이다. DOM 모듈과 비동기 클라이언트는 준비됐고 클라이언트 7건을 검증했다.

## 민원 생산자·AI 계약 대조
ai-01 5d2be81 classify.py: 관련성 보행안전 관련/비관련/불명, cls-2, 규칙/AI 방법. 확신도는 관련성 판단이며 위치 정확도 아님.
w07 4ed2cc7 dupes.py: 같은 행 N건/같은 제목 N건 표시. 파일 안에서만 세며 고유 중복군 ID가 아니다. ai01_port는 stub 결과를 분류 필드에 쓰지 않는다. 실제 적격 분류·집계 출력은 이번 작업에서 확보하지 못했다. 팀 미구현 판정 아님.
ai07 6c5e3bc engine_explainer.py는 official_use=False이며 score/rank_no/domain_scores/indicator_contributions가 모두 None인 적치물 예시만 허용한다. 점수 포함 현재 결과를 이 함수에 직접 연결하면 계약 위반이다. 점수 설명 소비 계약 확장이 필요하며 이 담당 코드는 변경하지 않았다. 다른 AI07 모듈 전체의 연결 가능성까지 배제한 판정은 아니다.

## 한계·다음 연결
공식 실행은 차단한다. 현재 EXPLORATORY_PROXY만 처리한다. 관측 상태·미산출을 보존하며 신뢰도/우선 확인/공식 후보를 생성하지 않는다. D-08/H-03 실제 반기쌍 없음. B-08 분모·사고 중복·방법론 미결 승계. 별도 조사 결과는 새 정책판본·새 회차와 회귀시험으로 반영한다.
SQLite 및 HTTP TestClient와 Node 시험이며 MySQL/브라우저/실제 LLM/팀 통합 완료가 아니다. 10/26 격리 계산→저장→조회 시연 가능, 실제 화면 시연은 추가 연결 필요. 10/30 재현 결과·미완료 발표 가능. 03~05용 코드·시험·설명 준비이며 제출 완료 아님.
