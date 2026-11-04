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

DB 스키마(SQL)는 이 저장소에 없고, 팀 구글 드라이브에 있습니다. 파일 이름은 `v2.5_261104_03_최종개발문서_DB백업쿼리포함`입니다. 접속 정보는 저장소에 올리지 않습니다.

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

**DB 준비**: 내 PC의 MySQL 8에 DB를 만들고 드라이브의 SQL 파일을 실행합니다. 공용 DB에 접속할 수 있으면 이 단계는 건너뜁니다.

> **주의**: 이 SQL은 `DROP TABLE` 후 `CREATE TABLE`을 합니다. 기존 데이터가 모두 지워지므로 공용 DB에는 실행하지 않습니다. DB(`CREATE DATABASE`)는 SQL에 없어서 아래처럼 먼저 만듭니다.

```bash
mysql -u root -p -e "CREATE DATABASE mysqlteam02db DEFAULT CHARACTER SET utf8mb4"
mysql -u root -p mysqlteam02db < v2.5_261104_03_최종개발문서_DB백업쿼리포함.sql
```

`.env`를 열어 값을 채웁니다. 내 PC의 DB를 쓰면 `RADAR_DB_HOST=127.0.0.1`입니다. 값은 저장소나 채팅에 올리지 않습니다.

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
SQL을 실행하면 로그인용 시험 계정 6개(`suj`, `jungwon`, `bundang`, `bundang-sidewalk`, `city`, `operator`)가 함께 들어갑니다. 시험용 비밀번호는 모두 `0000`입니다. 실제 운영에서는 쓰지 않습니다. 계정을 따로 만들 때는 `scripts/auth_create_test_users.py`를 쓰고, 사용법은 파일 맨 위에 있습니다.

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

## 문제 해결 (Troubleshooting)

| 증상 | 확인할 것 |
|---|---|
| 화면에서 서버 요청이 실패합니다 | 서버가 켜져 있는지, `VITE_API_BASE_URL` 주소와 포트가 맞는지, `.env`의 `RADAR_CORS_ORIGINS`에 화면 주소가 들어 있는지 봅니다 |
| `.env` 값이 적용되지 않습니다 | 파일이 저장소 루트에 있는지, 서버를 다시 켰는지 봅니다. 터미널에서 넣은 환경변수가 `.env`보다 우선합니다 |
| `/health/db`가 `unreachable`입니다 | DB 주소, 계정, 방화벽을 확인합니다. 공용 DB는 정해진 네트워크에서만 접속될 수 있습니다 |
| `Address already in use` | 포트 8000(서버) 또는 5173(화면)을 쓰는 다른 프로세스를 끄거나 `--port`로 바꿉니다 |
| `npm install`이나 빌드가 실패합니다 | `node -v`로 Node 22인지 확인합니다 |

## 기여하기 (Contributing)

브랜치, 커밋, PR 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 봅니다.
수치지형도 가공 테이블, 민원 테이블, `.env`는 저장소에 올리지 않습니다.

버전을 올릴 때는 세 곳을 같은 값으로 바꿉니다: `app/main.py`의 `version=`, `pyproject.toml`, `frontend/package.json`.
