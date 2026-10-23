# I-07 · AI-05 실제 함수 연결 — 2026-10-23

## 전체 흐름과 현재 위치

산정·분석은 별도 Chat, I-07은 Work에서 병렬 진행한다. 오늘 14시 팀 통합, 10/26 시연, 10/30 발표를 유지한다.
F-05(은경) 제안 → 62 승인·돌려보냄(I-07 진규) → AI-05 반영 함수(은경) → 87/88 → 감사·화면(규림).
현재: 실제 함수 연결, SQLite 검증, 격리 MariaDB 8건, 프론트 어댑터·DOM 상호작용 및 실제 HTTP 관통시험 완료. 실제 브라우저 시각 검증·팀 MySQL 환경·최신 develop 통합은 대기.
문서·시험 수를 전체 개발률 70%나 원본 15개 기능의 공식 완료로 환산하지 않는다.

## 사용 금지 기준

사용자가 명시한 이전 TEST_ONLY 점수·가정 입력·가정 산식과 그 히스토리는 이번 개발의 검토·승계·재사용 대상에서 제외한다. AI 개발 샘플을 실제 기능 개발 성과나 기준으로 사용하지 않는다.
현재 I-07은 제공된 팀 소스와 v2.1 테이블 계약만 사용한다. 이 기능의 HTTP/DB 검증용 임시 행은 점수 산정 샘플과 관련이 없다.

## 기준 소스

- feature-w05-core ZIP: `3bd89291e9e5926f0b26153bdcfaabf3cd7a7bda`
- feature-ai-05 ZIP: `3cc5cd50a27a8c0656f4e91da41f2a23070bfeaa`
- DB: 제공된 SQL v2.1의 62·70·87·88. 스키마 변경 없음.
- GitHub 서버 최신 커밋·main/develop 통합본은 직접 확인하지 못했다. ZIP의 근거 수준으로 기록한다.

AI-05는 실제 업로드 ZIP으로 확인했다. 같은 브랜치 ZIP에 공통 인증·감사 코드가 없어 W05 기준에 필요한 standards API·서비스를 가져와 연결했다. LLM/RAG를 새로 구현하지 않았다.

## 실제 함수 계약과 거래 경계

`app.services.standards.apply.apply_approved(sv_id: int, applied_by: int | None = None) -> dict`
`preview(sv_id)`는 읽기 전용 비교, `unapplied()`는 승인됐지만 87에 버전이 없는 제안 조회다. 은경이 추가 공유한 호출 설명도 같은 계약이며 재질문 없이 적용했다.

1. I-07: 62 행 잠금 → 제안 상태·종류 검증 → 승인자·시각·의견 갱신 → `audit.record(..., audit.APPROVAL, connection=con)` → commit.
2. 담당 부서 표 승인만 `apply_approved(id, user_id)` 호출. 함수가 별도 연결에서 87/88을 쓰고 자체 commit한다.
3. 반영 실패해도 앞선 승인·감사는 이미 커밋됐으므로 승인 상태를 제안으로 되돌리지 않는다.
4. 반영 중 DB 오류는 87/88 거래 rollback. commit 응답 유실은 적용 여부가 불명확하므로 성공·실패를 단정하지 않고 재조회·멱등 재시도로 확인한다.

가중치·기준값·우선 확인 조건은 승인 기록만 바꾼다. 부서표 함수나 재계산을 호출하지 않는다.
돌려보냄은 사유 필수, 255자 한도. 62에 원문 보존, 감사의 255자 칸에는 결정만 기록한다.
승인자 ID는 기존 JWT 문맥에서 취득한다. 임의 사용자 ID를 요청에 넣으면 거부한다.

## 은경 코드에 보완한 세 곳

기존 함수 이름·인자·반환·자체 commit 계약을 유지한다. 검토용 변경은 별도 패치에 분리했다.

- 반영에서 62 → 87 → 88을 FOR UPDATE로 잠근 뒤 현재 값을 읽는다. 기존 코드는 읽은 뒤 87 잠금을 얻어 대기 이전 스냅샷으로 판정할 여지가 있었다. MariaDB 10.11.14의 동일 제안·서로 다른 제안 경쟁 시험을 통과했다. 팀 MySQL 버전·다른 부하 조건은 별도 확인이 필요하다.
- 이미 반영된 번호라도 먼저 승인 상태를 확인한다. 미승인 행이 버전 포인터와 같다는 이유로 통과하지 않게 한다.
- 반영 후 부서가 공백이면 기존 content_format 오류로 막는다. 88 전체 삭제를 방지한다.

AI-05의 다른 기능과 원본 담당은 변경하지 않았다. 보완 내용은 은경 검토 대상으로 공유한다.

## API와 화면 담당자 전달 사항

모두 city(시 도로과) 권한. 토큰 없음 401, 다른 역할 403.

| 주소 | 용도 |
|---|---|
| GET /api/approvals?status=제안&limit=100 | 제안 목록; status는 제안·승인·돌려보냄 |
| GET /api/approvals/unapplied | 승인됐지만 미반영인 부서표 제안 |
| GET /api/approvals/{id} | 62 상세 |
| GET /api/approvals/{id}/preview | 실제 함수의 전·후·반영 예정 행; 쓰기 없음 |
| POST /api/approvals/{id}/review | {decision: 승인 또는 돌려보냄, reviewComment: 의견} |
| POST /api/approvals/{id}/apply | 승인된 부서표만 재시도; 승인 감사 중복 없음 |

응답은 기존 공통 camelCase. `X-Response-Case: snake`도 지원한다.
정상 반영은 `departmentApplied=true`와 함수 반환값 `application`을 포함한다.

| 실제 ApplyError 코드 | HTTP |
|---|---|
| not_approved, table_changed | 409 |
| needs_review, no_change, content_cut, content_format | 422 |
| not_jurisdiction | 400 |
| proposal_not_found, jurisdiction_not_found | 404 |

실제 함수의 status·code·message를 유지한다. 오류 예:

```json
{"error":{"status":409,"code":"table_changed","message":"제안한 뒤 담당 부서 표가 바뀌었습니다. 지금 표를 보고 다시 제안해 주세요","approvalStatus":"승인","departmentApplied":false,"applyStatus":"실패","retryUrl":"/api/approvals/1/apply"}}
```

임의 실행 오류는 503 department_apply_failed, `departmentApplied=null`, `applyStatus=확인 필요`로 응답한다.
승인 응답에서 이 오류가 발생했다면 `approvalStatus=승인`도 표시한다.
업무 오류를 해결하지 않은 동일 재요청은 같은 오류를 반환할 수 있다. 예를 들어 table_changed를 강제 덮어쓰지 않는다.
`unapplied()`는 과거에 적용됐다가 새 버전으로 대체된 제안도 포함할 수 있다. 미반영 목록을 모두 자동 재시도하지 않는다.

## 규림 화면 연결 변경

`VITE_I07_API=true`일 때 기존 로그인·승인 대기 화면을 실제 백엔드에 연결한다. 기본 미설정/false는 기존 화면 개발 모드다. 실제 요청 실패를 목업 성공으로 대체하지 않는다.

- 새 backend.js: Bearer JWT·공통 오류·401 세션 만료 처리. 비밀번호 저장 없음. sessionStorage의 토큰은 화면 세션 동안만 사용한다.
- session.js/AuthProvider: 기존 /api/auth/login·/me로 확인하고 오류를 화면에 표시한다. 현재 선택 연결 모드는 city 계정의 I-07 범위다. 다른 기능의 로그인/API 통합 완료를 뜻하지 않는다.
- approvals.js/reference.js: 62 목록과 미반영 제안, 실제 preview·승인·돌려보냄·재시도 매핑. 비부서표 설정은 content_ref 원문만 표시하며 가중치/영향 수치를 추측하지 않는다.
- ApprovalsPage: 승인과 반영 상태를 구분한다. 반영 실패 행을 다시 조회하고 재시도 경로를 제공한다. preview 실패 시 승인·반영을 막고 돌려보냄은 가능하다. 미반영 목록 전체를 자동 반영하지 않는다.
- RequireUser/UserLayout: 실제 연결 모드의 승인 화면만 회차 조회와 분리한다. I-07 실행을 위해 가짜 회차·점수·순위를 만들지 않는다. 기존 화면·공통 스타일을 사용하고 회차 선택이 필요 없는 상단만 구성했다.
- 현재 화면 개발 모드와 실제 연결 모드를 명시적으로 선택한다. 기능 전체가 실데이터에 연결됐다고 표시하지 않는다.

다음 실행 예시는 프론트 개발 서버를 새로 시작할 때 적용한다. API 주소에는 비밀번호를 넣지 않는다.

```powershell
# frontend 폴더
$env:VITE_I07_API = 'true'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm ci
npm run dev
```

백엔드는 기존 RADAR_DB_*를 적절한 개발 DB로 설정하고 저장소 루트에서 `uv run uvicorn app.main:app --port 8000`으로 실행한다. 브라우저는 기본 CORS 허용 주소인 http://127.0.0.1:5173에서 확인한다. 기존 팀의 실제 시 도로과 개발 계정을 사용하며 시험 계정을 운영 DB에 자동 생성하지 않는다.
빌드 시에도 VITE_I07_API 값이 들어가므로 값을 바꾸면 다시 빌드한다. 규림 검토 없이 전체 프론트의 기본 모드를 바꾸지 않는다.

## 실제 시험과 미검증

- 전체 87 PASS. I-07 HTTP/SQL 시험 39건, 기존 AI-05 함수 시험 5건, W05 기존 시험 43건.
- 실제 F-05 제안 API → I-07 → 은경 apply_approved → 87/88 경로를 SQLite 시험 DB에서 실행했다. 반영 함수를 모의 함수로 바꾸지 않았다.
- 정상·돌려보냄·권한·중복·같은 표의 두 제안·오류 계약·감사 실패·88 삽입 실패 후 원복·재시도를 확인했다.
- SQLite 어댑터는 %s·NOW()·FOR UPDATE·읽기 전용 시작문을 변환한다. MySQL 행 잠금 증거는 아니다.
- 최초 Unix 소켓 기동 차단 이후 TCP loopback으로 전환하고, 서버·시험을 같은 실행 환경에서 구동해 MariaDB 10.11.14의 8건을 모두 통과했다. 공용 DB에는 접속하지 않았다.
- 실제 DB 시험: 정상 반영·멱등 재시도, 동일 제안 동시 승인, 동일 부서표의 서로 다른 제안 경쟁 3건, 감사 실패 rollback, 반영 실패 후 복구, 최대 의견 길이. 8건 PASS. fixtures/i07의 62·70·87·88 CREATE TABLE은 제공된 v2.1 DDL 그대로, 사용자 FK 대상 60은 시험용 최소 PK 표다.
- 프론트 API 어댑터 12건 PASS. DOM의 로그인·승인·반영 실패·돌려보냄·재시도·원문 표시·세션 만료/토큰 누락을 7개 시나리오로 확인했다. Node 출력의 부모 테스트를 시나리오 수로 중복 계산하지 않는다.
- 실제 관통시험 1개 흐름 PASS: 운영자 실제 로그인 → F-05 API가 62 생성 → 화면 실제 로그인·JWT → I-07 승인 → 실제 은경 함수 → MariaDB 87/88 반영 → 승인 감사 1건. 실제 v2.1의 60/62/70/87/88 DDL로 만든 무작위 이름의 격리 DB를 정리했다. 가짜 HTTP 응답을 쓴 DOM 시험과 구분한다.
- CORS preflight에서 127.0.0.1:5173 허용 확인. frontend lint·기본 빌드·실제 연결 모드 빌드 통과.
- 후속 Chromium 153.0.8010.0 화면 시험: 응답 제어 방식으로 승인·돌려보냄·반영 실패·확인 필요·재시도·preview 실패·세션 만료·통신 실패 및 1280px 표시 9항목 PASS. 부모 테스트는 중복 집계하지 않는다. 원본 CSS 최소 폭 1280px 때문에 1024px 가로 스크롤은 별도 TODO 1건으로 남겼다.
- 실제 Chromium → 실제 로그인/JWT → 실제 HTTP API → 실제 은경 함수 → 격리 MariaDB 10.11.14 관통 1흐름 PASS. F-05가 만든 62의 승인자 22, 87의 설정 번호, 88의 보도팀 반영, 승인 감사 정확히 1건을 확인하고 시험 DB를 삭제했다. API 응답 제어 시험과 별도다.
- 1440px·1280px preview, 실패·확인 필요·승인 완료 화면을 직접 렌더링 확인했다. 팀 MySQL 환경·최신 팀 브랜치·규림의 최신 화면에 대한 통합 검증은 남아 있다.
- Starlette/httpx deprecation 경고 및 기존 프론트 번들 500kB 초과 경고가 있다. 이번 기능 때문에 전체 프론트를 재구성하지 않았다.

## 로컬 MySQL 추가 시험 (PowerShell)

운영 DB 이름이나 기존 RADAR_DB_*를 사용하지 않는다. 별도 로컬 인스턴스에서 CREATE/DROP DATABASE 권한이 있는 시험 계정으로 실행한다. 각 시험이 무작위 이름의 격리 DB를 만들고 정리한다.

```powershell
$env:RADAR_I07_MYSQL_TEST = '1'
$env:RADAR_I07_TEST_USER = '<로컬 시험 계정>'
$env:RADAR_I07_TEST_PASSWORD = '<시험 계정 비밀번호>'
$env:RADAR_I07_TEST_HOST = '127.0.0.1'
$env:RADAR_I07_TEST_PORT = '3306'
uv run python -m pytest -q tests/test_approvals_mysql.py
```

일반 회귀시험은 `uv run python -m pytest -q`. MySQL 전용 환경을 설정하지 않으면 8건을 명시적으로 건너뛴다.

## 협업·원본 업무·종료조건

- 은경: 실제 함수 거래 계약과 위 세 보완 검토. 공유 준비 완료, 회신 발송·합의는 미완료.
- 진규: I-07 연결 구현·SQLite/MariaDB·실제 HTTP/DOM/Chromium 검증 완료; 팀 MySQL 환경·최신 팀 화면/브랜치 통합 검증 남음. I-02는 승인 기록 연결만 진행.
- 규림: 준비된 최소 어댑터·화면 변경·선택 연결 모드를 검토하고 팀 UI에 반영. 실제 브라우저에서 배치·오류·재로그인을 확인. 응답·DOM·실제 DB 증거 첨부.
- 별도 Chat: D-01~D-04 등 실데이터 산정·분석 계속. 현재 Work는 산식·정책·77/78/82를 바꾸지 않았다.
- 원본 15개·공동 책임·데이터 생성/저장 책임·기존 승인/보류를 유지한다. 전체 공식 기능/평가 승인 상태를 자동 상향하지 않는다.

남은 종료조건: 최신 팀 소스와 충돌 확인 → 은경/규림 검토 → 팀 MySQL 환경·팀 최신 화면 실행 확인 → 팀 절차에 따른 통합. GitHub 업로드·병합·배포·공유 DB 변경은 아직 수행하지 않았다.

## 프론트 검증 명령

frontend에서 `npm run test:i07`, `npm run lint`, `npm run build`를 실행한다.
선택 DOM 시험은 jsdom이 필요하며, `npm install --prefix <임시 디렉터리> --no-save jsdom` 후 RADAR_I07_DOM_RUNTIME을 그 디렉터리로 설정해 `npm run test:i07:dom`을 실행한다. jsdom이 없으면 명시적으로 건너뛰며 통과로 계산하지 않는다. 기존 프로젝트 의존성·lockfile은 바꾸지 않고 테스트 스크립트만 추가했다.
실제 HTTP 관통용 DOM 모드는 자체 생성한 격리 서버·무작위 시험 계정으로만 실행하며 운영 서버를 대상으로 실행하지 않는다.

실제 HTTP 관통시험은 위 MySQL 시험 환경과 RADAR_I07_DOM_RUNTIME 설정 후 저장소 루트에서 `uv run python tests/run_i07_live.py --output-dir <시험 결과 디렉터리>`로 재현할 수 있다. 이 도구는 별도 로컬 DB에 무작위 이름의 DB·계정을 만들고 실제 F-05 API·로그인·I-07·87/88·감사를 확인한 뒤 정리한다. 운영 DB 이름을 인자로 받지 않는다.

## 실제 브라우저 재현과 팀 통합 기준

브라우저 시험은 프로젝트 외부에 playwright-core를 설치하고 설치된 Chrome/Chromium 경로를 명시한다. Windows 예시의 실행 파일 경로는 본인 PC에 존재하는 값으로 바꾼다. 의존성·lockfile은 바꾸지 않는다.

```powershell
$i07BrowserTools = Join-Path $env:TEMP 'radar-i07-browser-tools'
npm install --prefix $i07BrowserTools --no-save playwright-core
$env:RADAR_I07_BROWSER_RUNTIME = $i07BrowserTools
$env:RADAR_I07_CHROMIUM_PATH = '<설치된 Chrome 또는 Chromium 실행 파일>'
$env:RADAR_I07_BROWSER_TEST = '1'
# frontend 폴더에서 응답 제어 화면 시험
npm run test:i07:browser
# 저장소 루트에서 위 별도 MySQL 시험 환경을 설정한 뒤 실제 브라우저 관통시험
uv run python tests/run_i07_live.py --browser --output-dir '<시험 결과 디렉터리>'
```

실제 브라우저 관통시험은 127.0.0.1:5173을 사용한다. 이미 사용 중이면 해당 서버를 직접 확인하고 별도 시험 환경에서 실행한다. 응답 제어 시험은 임시 포트를 사용한다. 브라우저 경로·시험 도구가 없을 때 실행을 켜면 실패하며, 실행을 켜지 않은 선택 시험은 SKIP이므로 PASS로 계산하지 않는다.

- 자기 기능 브랜치에서 최신 feature/w05-core와 feature/w05-llm을 반영한다. w05-llm은 전달받은 d88744f를 포함하는지 확인한다. 서버 최신본은 현재 접근 차단이라 직접 검증하지 못했다.
- pyproject.toml·uv.lock은 I-07에서 바꾸지 않았다. 충돌 시 core 기준에 기능 패키지만 보존하고 uv lock을 재생성한다. frontend/package.json은 시험 명령만 추가했으며 package-lock.json은 바꾸지 않았다.
- app/main.py는 APPROVALS 라우터를 정확히 한 번 보존한다. access_audit.py의 connection 선택 인자, standards/apply.py 보완, 프론트 인증·세션·레이아웃 파일은 담당자 변경을 보존하며 합친다.
- llm_tasks.toml·LLM 문서는 최신 llm 기준에 개별 추가 내용을 보존한다. keep_alive 30분·대기 120초는 전달받은 변경이며 실제 코드 확인은 미완료다. I-07에서 call_llm을 호출하지 않으므로 새 의존성을 추가하지 않는다. 공용 OLLAMA_BASE_URL은 팀에서 받은 값을 각자 .env에 설정한다.
- 전체 패치·기존 패키지별 증분 패치는 하나만 선택한다. AI05 안전 보완은 전체/증분 패치에 포함되므로 중복 적용하지 않는다. 최신 소스에는 먼저 git apply --check로 확인하고 충돌 시 files/를 통째로 덮어쓰지 않는다.
- 산정 설정 생성·형식, 승인 설정 선택, 62와 77의 버전 대응은 병렬 1 실제 계약 확인 후 연결할 미결이다. 이 때문에 독립적인 I-07 통합 작업을 중단하지 않는다. 77/78/82·07~10·회차/재계산/근거 공동 책임은 별도 점검표를 유지한다.
