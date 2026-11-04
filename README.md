# RADAR 2.0

성남시 보행 안전 정기 점검의 우선순위를 제안하는 도구입니다.
민원을 처리하는 도구가 아닙니다. 먼저 점검할 곳을 고르는 참고 순위를 보여 줍니다.

- 기술 스택: React 19 · Vite 7 (프론트엔드), FastAPI · Python (백엔드), MySQL 8 (DB)
- 핵심 흐름: 점검 후보 보기 → 근거 확인 → 점검 여부 결정 → 우선 점검 대상 확정 → 점검 요청서 받기

| 사용자 | 하는 일 |
|---|---|
| 구 도로관리팀 | 점검 후보를 보고 우선 점검 대상을 정합니다 |
| 시 도로과 | 3개 구의 후보와 확정 현황을 봅니다 |
| RADAR 운영자 | 회차, 기준정보, 데이터, 계정을 관리합니다 (어드민) |

## 요구 사항 (Prerequisites)

| 도구 | 버전 | 어디에 쓰나요 |
|---|---|---|
| Node.js | 22 (`frontend/.nvmrc`) | 프론트엔드 |
| Python | 3.11 ~ 3.13 | 백엔드 |
| [uv](https://docs.astral.sh/uv/) | 최신 | 파이썬 패키지와 가상환경 관리 |
| MySQL 서버 접속 정보 | 8 | 백엔드 (프론트엔드만 볼 때는 필요 없음) |
| Ollama 또는 Gemini API 키 | - | AI 기능을 직접 돌릴 때만 (선택) |

DB 스키마(SQL)는 이 저장소에 없고, 팀 구글 드라이브의 `v2.5_261104_03_최종개발문서_DB백업쿼리포함` 파일에 있습니다. 실행 방법은 아래 '백엔드 실행'을 봅니다.

## 시작하기 (Getting Started)

저장소를 받은 뒤 시작합니다.

```bash
git clone https://github.com/gyurim027/AXI_RADAR_2.0_2026.git
cd AXI_RADAR_2.0_2026
```

### 1. 프론트엔드만 실행 (서버·DB 없이)

가짜 서버(mock)로 돌아서 화면 전체를 볼 수 있습니다.

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 을 엽니다. 로그인 화면의 연습용 계정은 [frontend/README.md](frontend/README.md)에 있습니다.

### 2. 백엔드 실행

저장소 루트에서 합니다.

```bash
uv sync                    # 의존성 설치 (.venv 생성)
cp .env.example .env       # Windows PowerShell: Copy-Item .env.example .env
```

**DB 준비**: 내 PC의 MySQL 8에 DB를 만들고 드라이브의 SQL 파일을 실행합니다. DB 자체(`CREATE DATABASE`)는 SQL에 없어서 먼저 만듭니다.

> **주의**: 이 SQL은 `DROP TABLE` 후 `CREATE TABLE`을 하므로 기존 데이터가 모두 지워집니다. 공용 DB에는 실행하지 않습니다. 공용 DB를 쓸 때는 이 단계를 건너뜁니다.

```bash
mysql -u root -p -e "CREATE DATABASE mysqlteam02db DEFAULT CHARACTER SET utf8mb4"
mysql -u root -p mysqlteam02db < v2.5_261104_03_최종개발문서_DB백업쿼리포함.sql
```

`.env`를 열어 값을 채웁니다. 내 PC의 DB를 쓰면 `RADAR_DB_HOST=127.0.0.1`로 둡니다.
`.env`의 값은 저장소나 채팅에 올리지 않습니다.

| 항목 | 설명 |
|---|---|
| `RADAR_DB_HOST`, `RADAR_DB_PORT`, `RADAR_DB_USER`, `RADAR_DB_PASSWORD`, `RADAR_DB_NAME` | DB 접속 정보 |
| `RADAR_JWT_SECRET` | 로그인 토큰 서명 키 (긴 임의 글자). 개발 중에 비우면 서버를 켤 때마다 임시 키를 씁니다 |
| `RADAR_CORS_ORIGINS` | 프론트엔드 주소. 기본값은 `http://localhost:5173` |
| `OLLAMA_BASE_URL`, `GEMINI_API_KEY` | AI 기능을 직접 돌릴 때만 |

나머지 항목은 `.env.example`의 주석을 봅니다.

```bash
uv run uvicorn app.main:app --port 8000
```

- http://127.0.0.1:8000/docs : API 문서 (제목 옆에 서버 버전이 보입니다)
- http://127.0.0.1:8000/health : 서버 상태. DB를 설정하지 않았으면 `db_configured`가 `false`입니다
- http://127.0.0.1:8000/health/db : DB 연결 확인

DB 없이도 서버는 켜지지만 로그인과 데이터 조회는 DB가 있어야 합니다.
SQL을 실행하면 로그인용 시험 계정 6개가 함께 들어갑니다: `suj`, `jungwon`, `bundang`, `bundang-sidewalk`, `city`, `operator`.
시험용 비밀번호는 모두 `0000`이고, 실제 운영에서는 쓰지 않습니다.
계정을 따로 만들 때는 `scripts/auth_create_test_users.py`를 쓰고, 사용법은 파일 맨 위에 있습니다.

### 3. 프론트엔드와 백엔드 연결

`frontend/.env.local` 파일을 만들고 서버 주소를 적습니다.

```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEV_LOGIN_PASSWORD=0000
```

`VITE_DEV_LOGIN_PASSWORD`를 넣으면 개발 서버의 로그인 화면에 있는 개발용 간편 로그인 버튼으로 바로 들어갈 수 있습니다. 넣지 않으면 아이디와 비밀번호를 직접 입력합니다.

그다음 `npm run dev`를 다시 실행합니다. 서버 주소가 있으면 서버 연결 모드가 되고, 아직 서버와 연결되지 않은 화면에는 안내 문구가 나옵니다. 가짜 데이터를 보여 주지 않습니다. 이 줄을 지우면 1번의 가짜 서버 모드로 돌아갑니다. 옵션은 `frontend/.env.example`에 있습니다.

## 주요 기능

- **점검 후보**: 회차별 점검 후보 목록, 지도, 후보 상세(점검 필요도, 근거, 민원, 조치 제안)
- **결정과 확정**: 후보별 점검 여부 결정, 구 단위 확정, 점검 요청서
- **어드민**: 회차 관리, 승인 대기, 산정 기준, 계정, 접속 기록, 알림 설정
- **AI**: 민원 정제(AI-01), 위치 보정(AI-03), 관련 법 조문 찾기(AI-05), 설명문(AI-07), 조치 제안 초안(AI-10)
- 핵심 시나리오(점검 후보 보기 → 근거 확인 → 결정 → 구 확정 → 점검 요청서)에 필요한 기능은 서버 연결 모드에서 동작합니다. 일부 부가 화면과 AI 기능은 서버와 아직 연결 중입니다. 기준은 기능정의서 최신 버전입니다.

## 프로젝트 구조

```
화면 (React, :5173)  →  공통 서버 (FastAPI, :8000)  →  MySQL
                                   └→  공통 LLM 모듈 (Ollama · Gemini)
```

| 경로 | 내용 |
|---|---|
| `frontend/` | 화면. 사용자(`src/user`), 어드민(`src/admin`), 서버 호출(`src/api`), 가짜 서버(`src/mocks`) |
| `app/api/` | 기능별 API (`/api/<기능>`) |
| `app/services/` | 기능별 처리 로직 (AI, 산정, 확정 등) |
| `app/core/` | 설정, DB, 로그인, 공통 LLM 모듈 |
| `scripts/` | 데이터 적재, 시험 계정 만들기 같은 실행 스크립트 |
| `data/` | 기능이 쓰는 기준 자료 |
| `tests/` | 백엔드 시험 |
| `docs/` | 서버 구조와 기능별 문서 ([서버 공통 구조](docs/W05_common_structure.md)) |

## Workflow

RADAR가 순서대로 거치는 전체 단계입니다. 핵심은 점검 후보를 만들고 확정하는 흐름이고, 부가는 없어도 핵심이 돌아가는 단계입니다.

| 단계 | 하는 일 (기능 ID) | 실행 위치 | 구분 |
|---|---|---|---|
| 1. 기준 자료 | 법령 색인(AI-05), 격자·시설 특징(B-02), 산정 기준 제안과 승인(I-02·I-07) | `scripts/ai05_build_index`, `scripts/grid_build_feature`, `/api/settings`, `/api/approvals` | 부가 (처음과 반기마다) |
| 2. 민원 적재 | 월별 xlsx 등록(C-09), 민원 정제(AI-01), 분류 검수(C-08) | `/api/c09/uploads`, `scripts/load_month.py`, `/api/c08` | 핵심 |
| 3. 위치 보정 | 위치 글자로 좌표·격자 찾기(AI-03) | `scripts/ai03_locate`, `scripts/ai03_apply` | 핵심 |
| 4. 입력 판본 | 입력 판본 등록과 원천 감사 승인 | `/api/input-builds` | 핵심 |
| 5. 회차 만들기 | 입력 검증 후 회차 생성(D-10) | `/api/d10/rounds` | 핵심 |
| 6. 점수 산정 | 분류, 반복 민원(C-07), 점수, 순위 | `scripts/run_official_priority` | 핵심 |
| 7. 점검 후보 보기 | 목록, 지도, 상세, 근거 설명문(AI-07), 관련 조문(AI-05), 데이터 문제 | `/api/priority`, `/api/ai07`, `/api/ai05`, `/api/data-issues` | 핵심 |
| 8. 결정과 확정 | 후보 결정(G-03), 구 확정(G-06) | `/api/g03`, `/api/g06` | 핵심 |
| 9. 점검 요청서 | 요청서 미리보기(H-01) | `/api/h01` | 핵심 |
| 10. 조치 제안 | 초안 생성(AI-10), 운영자 검토와 승인 후 후보 상세에 표시 | `/api/ai10`, `/api/priority` | 부가 (승인 전에는 비어 있음) |
| 11. 운영 | 계정과 접속 기록(I-01·I-04), 실패 알림 메일(I-03), 실행 기록과 대시보드(I-05·I-06) | `/api/auth`, `/api/admin`, `/api/ops` | 부가 |

단계 막힘은 아래 Troubleshooting에서 오류 코드로 찾습니다.

## 테스트

```bash
uv run pytest                      # 백엔드 (저장소 루트)
```

```bash
cd frontend
npm run lint                       # 코드 검사
npm run build                      # 배포용 빌드
node --test tests/*.test.*         # 프론트엔드 테스트
```

## Troubleshooting

오류 응답의 `code` 값이나 서버 로그의 글자를 그대로 검색합니다: `grep -rn "<키워드>" app/`. 요청 하나를 따라갈 때는 응답 헤더 `X-Request-ID`로 서버 로그를 찾습니다.

| 단계 | 증상·키워드 | 원인 | 조치 |
|---|---|---|---|
| 실행 | `Address already in use` | 포트 8000(서버)이나 5173(화면)을 다른 프로세스가 쓴다 | 그 프로세스를 끄거나 `--port`로 바꿉니다 |
| 실행 | `npm install`이나 빌드 실패 | Node 버전이 다르다 | `node -v`로 22인지 확인합니다 |
| 실행 | 화면에서 서버 요청 실패 (CORS) | 서버가 꺼져 있거나 주소가 다르다 | 서버를 켜고, `VITE_API_BASE_URL`과 `.env`의 `RADAR_CORS_ORIGINS`를 맞춥니다 |
| 설정 | `.env` 값이 안 먹는다 | 파일 위치나 환경변수 우선순위 | `.env`는 저장소 루트에 둡니다. 터미널 환경변수가 `.env`보다 우선합니다. 서버를 다시 켭니다 |
| DB | `db_not_configured` (503), `db_configured: false` | `.env`에 DB 접속 값이 없다 | `RADAR_DB_HOST`, `RADAR_DB_USER` 등을 채우고 서버를 다시 켭니다 |
| DB | `/health/db`가 `unreachable`, `db_read_failed` | 주소, 계정, 방화벽 문제. 공용 DB는 정해진 네트워크에서만 접속된다 | 접속 값을 확인하거나 내 PC의 MySQL에 SQL을 실행해 씁니다 |
| DB | `setting_table_missing`, `decision_schema_unavailable` | DB에 표가 없다 (SQL 버전이 낮다) | 최신 SQL(`v2.5`)로 표를 다시 만듭니다. 이 SQL은 데이터를 지웁니다 |
| 로그인 | `login_required`, `token_expired`, `role_changed` | 로그인이 없거나 시간이 지났거나 역할이 바뀌었다 | 다시 로그인합니다 |
| 로그인 | `wrong_password`, `account_locked` (423) | 비밀번호를 여러 번 틀려 잠겼다 | 잠금 시간이 지난 뒤 다시 합니다. 운영자가 어드민에서 임시 비밀번호를 다시 만들면 잠금도 풀립니다 |
| 로그인 | `inactive_account` | 사용 중지된 계정이다 | 운영자가 어드민에서 계정을 `사용 중`으로 바꿉니다 |
| 권한 | `forbidden_role`, `forbidden_gu` | 역할이나 담당 구가 맞지 않는다 | 맞는 계정으로 로그인합니다 (구 팀은 자기 구만 봅니다) |
| 민원 적재 | `too_large` (413), `empty_file`, `invalid_input` | 파일이 크거나 비었거나 입력이 틀렸다 | 한 달치 xlsx인지, 공식 원본 여부 선택이 맞는지 확인합니다 |
| 민원 적재 | `load_failed` (500) | 적재 중 검사에 걸렸다 | 업로드 기록의 검사 결과를 봅니다 |
| 회차 | `run_not_found` (404) | 회차가 없다 | 회차 번호를 확인합니다. 회차가 없으면 운영자가 만듭니다 |
| 회차 | `run_scope_missing` (503) | 회차에 민원 자료 기간(시작·끝)이 비어 있다 | 회차 생성 때 넣은 기간을 확인합니다 |
| 산정 | `already_running` (409) | 같은 실행이 이미 돌고 있다 | 끝난 뒤 실행 기록을 확인합니다 |
| 산정 | `rerun_not_supported`, `rerun_input_missing` | 화면에서는 다시 실행할 수 없다 | 터미널에서 `scripts/run_official_priority`로 다시 돌립니다 |
| 입력 판본 | `input_build_lookup_blocked` (409) | 입력 판본 조회가 막혔다 | 응답 메시지에 이유가 나옵니다. 원천 감사 승인 상태를 확인합니다 |
| 후보 | `candidate_not_found` (404), `gu_required` (422) | 그 회차에 격자가 없거나 구를 안 정했다 | 회차와 격자 번호, 구 선택을 확인합니다 |
| 결정·확정 | 403 "개발용 API 비활성화" | `AI_G03_DEV_API_ENABLED`, `AI_G06_DEV_API_ENABLED`가 `1`이 아니다 | `.env.example`을 복사했는지 확인하고 서버를 다시 켭니다 |
| 결정·확정 | 서버를 다시 켰더니 결정이 사라졌다 | `RADAR_G03_PERSIST_ENABLED=0`이면 결정을 메모리에만 둔다 | 현재 알려진 동작입니다. 운영 DB 연동이 끝나기 전까지 `.env.example`대로 `0`으로 둡니다 |
| AI | `local_access_only` (403) | 설명문 일부 API는 서버 PC에서만 열린다 | 서버가 켜진 PC에서 호출합니다 |
| 화면 | "아직 서버와 연결되지 않았습니다" | 서버 API가 아직 없는 화면이다 | 오류가 아니라 정상 안내입니다 |
| 화면 | 후보 상세의 조치 제안이 비어 있다 | 승인된 조치 제안이 아직 없다 | 승인 전에는 비어 있습니다. 점검 요청서는 조치 제안 없이도 나옵니다 |

## Contributing

브랜치, 커밋, PR 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 봅니다.
수치지형도 가공 테이블, 민원 테이블, `.env`는 저장소에 올리지 않습니다.

버전을 올릴 때는 세 곳을 같은 값으로 바꿉니다: `app/main.py`의 `version=`, `pyproject.toml`, `frontend/package.json`.
