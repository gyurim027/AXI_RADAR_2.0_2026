# W05 공통 구조 규칙 (W05-01 · W05-03)

RADAR 2.0 백엔드는 **FastAPI 서버 하나**(포트 8000)에 기능별 API를 붙인다. 이 문서는 그 규칙이다. 담당: 은경 · 2026-10-21 · 기준: 기능정의서 v0.5.3, 통합 기획·관리 대장 v0.4.2, 파트 분배 정리 v5.8, 팀 답변(10/21)

## 1. 실행

저장소 루트, PowerShell 기준.

```powershell
uv sync                                       # 기본 묶음 설치 (공통 서버 + AI-05·07·10)
uv sync --extra ai03                          # AI-03 배치를 돌릴 사람만 추가
Copy-Item .env.example .env                   # 처음 한 번, 값은 직접 채움 (.env는 올리지 않음)
uv run uvicorn app.main:app --port 8000       # 서버 켜기 → http://127.0.0.1:8000/docs
uv run python -m pytest tests                 # 시험 (실제 DB 없이 도는 것 위주)
```

- `/health`: 서버가 떠 있는지와 붙은 기능 목록 (DB는 연결하지 않음)
- `/health/db`: 공용 DB에 실제로 붙는지 (`ok` / `unreachable` / `not_configured`)

## 2. 폴더

| 경로 | 넣는 것 |
|---|---|
| `app/main.py` | 서버 하나. 기능 라우터를 `ROUTER_MODULES`에 한 줄씩 적는다 (그 브랜치에 아직 없는 기능은 자동으로 건너뜀) |
| `app/api/<기능>_<이름>_api.py` | 주소(라우터)만. 예: `ai05_law_api.py` |
| `app/services/<기능>/` | 본체 로직. 예: `app/services/ai05/` |
| `app/core/` | 공통 부품: `config.py`(설정) · `db.py`(공용 DB) · `responses.py`(응답·오류 형식) · `request_log.py`(요청 로그) · `auth.py`(로그인·권한, I-01) · `access_audit.py`(접근 기록, I-04) · `llm.py`(W05-05, 규림) |
| `data/<기능>/` | 기능에 꼭 필요하고 **공개 자료로 만든** 작은 파일만 |
| `data/private/` | 올리면 안 되는 자료를 내 PC에 둘 곳 (저장소에 안 올라감) |
| `scripts/<기능>_*.py` | 배치(정해진 때 돌리는 실행 파일) |
| `tests/test_<기능>_*.py` | 시험 |
| `docs/<기능>/` | 기능 설명 |

파일·폴더 이름은 영어 (CONTRIBUTING). 지금 `app/services/ai10_*.py`는 예전 위치 그대로이고, 나중에 `app/services/ai10/`로 옮긴다.

## 3. 새 기능 붙이기

1. `app/services/<기능>/`에 본체를 만든다.
2. `app/api/<기능>_<이름>_api.py`에 `router = APIRouter(prefix="/api/<기능>", tags=[...])`.
3. `app/main.py`의 `ROUTER_MODULES`에 `("AI-xx", "app.api.<파일 이름>")`이 있는지 본다. 없으면 PR 설명에 적어 두면 합칠 때 넣는다 (공통 파일은 각자 고치지 않음).
4. `tests/`에 시험을 넣고 `uv run python -m pytest tests`가 통과하는지 본다.

## 4. 주소·응답·오류

- 주소: `/api/<기능>/...` (예: `/api/ai05/related`, `/api/ai07/db/runs`, `/api/ai10/reviews`)
- 칸 이름: **DB·파이썬 코드는 snake_case**(SQL v2와 같게). **화면에 주는 응답은 camelCase** — 공통 서버가 `/api/` 응답을 자동으로 바꾼다(`law_name` → `lawName`). 한글 키, `CK-09` 같은 키, 값은 바꾸지 않는다. 백엔드끼리 원래 이름이 필요하면 요청 머리에 `X-Response-Case: snake`.
- 오류는 한 모양: `{"error": {"status": 404, "code": "not_found", "message": "..."}}`. 기능 코드에서는 `raise ApiError(400, "invalid_run", "설명")` (`app/core/responses.py`). message에 비밀번호·SQL·원문·예외 상세를 넣지 않는다.
- CORS: `.env`의 `RADAR_CORS_ORIGINS`(기본 `http://localhost:5173`).

## 5. DB

- 접속은 `app/core/db.py` 하나. 접속 정보는 `.env`의 `RADAR_DB_HOST / PORT / USER / PASSWORD / NAME`에만 (화면 입력·코드에 적기·`local.env` X).
- 조회만 할 때 `db.read_only(sql, args)` (읽기 전용 거래), 쓸 때 `with db.connect() as con:` 후 `con.commit()`.
- 값은 항상 `%s` 자리표시자로. SQL 문자열에 값을 이어 붙이지 않는다.
- 기준 자료는 CSV 스냅샷 대신 DB 표에서 읽는다.
- 공용 DB는 진규님 PC(항상 켜 둠), 강의실 네트워크에서만 접속된다. 밖에서는 내 PC MySQL에 SQL v2를 띄우고 `.env`만 바꾼다.
- 표 구조를 바꿔야 하면 은경에게 요청 → SQL v2.x로 올린다 (W05-02).

## 6. 외부 AI·외부 API

- 외부 AI 전송은 대장 06 데이터 목록 "외부 AI 전송" 칸을 따른다. **미확인이면 내부 모델(Ollama)만** (POL-021). 가리기 전 민원 원문은 외부로 보내지 않는다 (POL-008).
- LLM은 공통 모듈 `app/core/llm.py`(W05-05, 규림)로 부른다. 기본은 내부(Ollama), 외부(Gemini)는 작업 설정과 자료 허용이 둘 다 맞을 때만, Ollama가 꺼지면 외부로 넘기지 않고 실패. 환경변수: `OLLAMA_BASE_URL`, `GEMINI_API_KEY`, `LLM_DEFAULT_ROUTE`. 작업별 모델은 `app/core/llm_tasks.toml`.
- 브이월드: 사전 승낙(10/15)으로 변환 좌표 DB 저장 가능 · 화면에 "국토교통부 브이월드" 출처 표시 · 대량·배치 호출은 제한될 수 있어 새 주소만 나눠서 부른다.
- 서버·DB는 국내에만 둔다 (브이월드 해외 IP 차단, 수치지형도 국외 반출 금지 — 공간정보관리법 제16조·제21조).

## 7. 로그

요청마다 JSON 한 줄(`app/core/request_log.py`): `ts · request_id · method · path · status · duration_ms · module · user_id · role · error_code`.
요청·응답 본문, 쿼리 문자열, 비밀번호·토큰, 민원 원문, 예외 상세는 남기지 않는다 (ISS-032). `request_id`는 응답 머리 `X-Request-ID`로도 돌려주고, LLM 모듈 로그도 같은 값을 남겨 이어 붙인다. 법정 접속기록(I-04)은 이 로그와 별도로 70 `access_audit`에 남긴다.

## 8. 브랜치와 합치기 (금요일 14시)

- 각자 `feature/<기능>` 브랜치에서 **자기 폴더만** 고친다: `app/api/<기능>_*.py`, `app/services/<기능>/`, `data/<기능>/`, `scripts/<기능>_*.py`, `tests/test_<기능>_*.py`, `docs/<기능>/`.
- 공통 파일(`app/main.py`, `app/core/`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore`)은 고치지 않는다. 필요한 패키지·환경변수·라우터 줄은 PR 설명에 적는다.
- 미리 돌려 보려면 내 브랜치에서 `git merge origin/feature/w05-core` (develop에는 금요일 전까지 아무것도 합치지 않음).
- 금요일: `feature/w05-core` → `feature/w05-llm`(공통 LLM 모듈) → 기능 브랜치 하나씩. 하나 합칠 때마다 `uv run python -m pytest tests`와 `/health` 확인.

## 9. 저장소에 올리면 안 되는 것

`.env`·`local.env`, 수치지형도 원본·가공 자료, 개인정보·민원 자료(민원에서 뽑은 샘플 포함), 캐시(`out/`, `*_cache.json`). 필요하면 `data/private/`(무시됨)에 둔다.

## 10. 로그인·권한 (I-01)과 접근 기록 (I-04) — 초안 v0.1

**화면 쪽**
- `POST /api/auth/login` `{"loginId", "password"}` → `{"token", "tokenType": "Bearer", "expiresIn", "user": {"id", "role", "gu", "org", "name", "readOnly"}}` (목업 `publicUser` 모양, role = `district` / `city` / `operator`)
- 이후 모든 요청 머리에 `Authorization: Bearer <token>`. `GET /api/auth/me`로 지금 사용자 확인. 로그아웃은 토큰을 버리면 됨.
- 실패: 401 `wrong_password`(+ `remaining` 남은 횟수, `lockMinutes`) · 423 `account_locked`(5번 틀리면 10분) · 403 `inactive_account` · 401 `login_required` / `token_expired`(다시 로그인)

**기능 API 쪽** (`app/core/auth.py`, `app/core/access_audit.py` 맨 위 설명 참고)
- 로그인만 확인: `user: dict = Depends(current_user)` → `user["user_id"]`, `user["role"]`, `user["gu"]`
- 역할 제한: `dependencies=[Depends(require_roles("city"))]`
- 구 제한: `allowed_gus(user)` (구 도로관리팀은 자기 구만), 다른 구 요청은 `check_gu(user, gu)`가 403
- 접근 기록: 민원 점 위치는 `access_audit.complaint_points(request, user, gu, reason)` (로그인 한 번 동안 구·업무 목적마다 한 줄), 파일 내려받기·결정·승인·설정 변경은 `access_audit.record(request, user, 종류, key)`. 로그인은 자동.
- 비밀번호는 해시(scrypt)만 저장. 시험 계정 6개: `scripts/auth_create_test_users.py` (비밀번호는 `RADAR_SEED_PASSWORD`로만)

## 11. 실행 기록 (I-06) · 실패 알림 (I-03) · 운영 대시보드 (I-05) — 초안 v0.1, SQL v2.1 필요

**각 기능(배치·API)에서** — 돌릴 때마다 감싸기만 하면 85 `job_run`·86 `job_run_log`에 남고, 실패하면 71 `alert_delivery`에 운영자 알림이 생긴다.
```python
from app.core.job_run import track, JobFailed
with track("좌표", "2026 하반기 민원 좌표", module="AI-03") as job:   # 종류: 수집·업로드·검사·좌표·분류·산정·설명문·조치 제안·색인
    job.log("주소 2,546건을 읽었습니다")       # 단계 한 줄 (원문·개인정보·SQL X)
    job.rows(2546)                            # 처리 건수 · job.warn("…") 이면 '경고'로 끝남
raise JobFailed("missing_column", "보도 면적 열이 비어 있음")       # 화면에 보여도 되는 실패 원인
```
상태: 실행 중 · 성공 · 경고 · 실패 · 건너뜀 (화면 목업과 같음). 다른 예외는 원인 칸에 예외 종류만 남는다. 기록이 실패해도 본래 작업은 계속된다.

**화면 쪽 (RADAR 운영자만)**: `GET /api/ops/dashboard` · `GET /api/ops/runs?days=30&status=실패` · `GET /api/ops/runs/{id}`(단계 기록 포함) · `GET /api/ops/notifications` · `POST /api/ops/notifications/{id}/read`

## 12. 공통 평가 틀 (W05-06) — 초안 v0.1

- 정답 목록: `data/eval/<기능>_cases.csv` (칸: case_id · 입력 · 기대 답 · 맞음 기준 · 메모). 맞음 기준 = 같음 · 포함 · 안 들어감 · 아님 · N등 안 · 못 찾음. 민원 원문·개인정보 넣지 않음.
- `안 들어감`은 빈 결과를 틀림으로 센다 (AI-07·AI-01 가림). `아님`은 "이 값을 내면 오답, 못 찾은 건 오답 아님" (AI-03 사람 검수 '틀림').
- 점수표에 같이 나오는 값: 결과 낸 수 · 오연결(결과를 냈는데 틀림) · **오연결률 = 오연결 / 결과 낸 수** · 찾은 비율 = 찾아야 하는 문제(같음·포함·N등 안) 중 결과를 낸 비율. AI-03은 두 값을 함께 본다(10/23 세은).
- 어댑터: 각 기능이 `app/services/<기능>/eval_adapter.py`에 `run(입력) -> 결과` 하나 (예: AI-05)
- 실행: `uv run python -m scripts.eval_run --name ai05 --cases data/eval/ai05_cases.csv --adapter app.services.ai05.eval_adapter:run` → 요약은 화면, 자세한 결과는 `out/eval/`

## 12-1. 우선순위 결과 조회 (77·78·82) — 초안 v0.1, 10/23

- 계산·후보 선정은 진규 산정 기능이 77 `priority_run`·78 `priority_candidate`에 쓴다. 이 API는 **읽기만** 한다 (`app/services/priority/`, `app/api/priority_api.py`).
- `GET /api/priority/runs` · `GET /api/priority/runs/{runId}/candidates?gu=&selected=Y&limit=&offset=` · `GET /api/priority/runs/{runId}/candidates/{gid}` (82 조치 제안 포함)
- 로그인한 사람 모두. 구 도로관리팀은 자기 구만 (구는 05 `id_gu`에서 '성남시 '를 뗀 이름). 구가 빈 격자 44개는 시 도로과·RADAR 운영자만 봄.
- NULL은 NULL 그대로. 점수가 없으면 `scoreStatus: "미산출"` (0점으로 바꾸지 않음). 순위 없는 격자는 목록 뒤로.
- 78 상세 5칸(진규 추가안 `78_상세칸_추가안_운영미적용.sql`)은 아직 DB에 없음 → `details.stored=false`, 모두 null. v2.2에서 칸이 생기면 여기서 읽도록 바꾼다.
- `runId`는 숫자 (77 BIGINT). 글자면 422.

## 13. 남은 것 (로그인·운영)
- 60 `app_user`에 `failed_count`·`locked_until` 칸 (SQL v2.1). 칸이 없으면 잠금 횟수를 서버 메모리에 둠(다시 켜면 초기화). 칸을 더한 뒤에는 서버를 다시 켠다.
- 70 `access_audit` 수정·삭제를 DB에서 막는 트리거 (공용 DB 권한 확인 뒤)
- 계정 만들기·역할 바꾸기 API (어드민 계정 화면, 61 `role_change_log`)
- API마다 어느 역할이 쓰는지 (각 기능 담당이 PR에 적기)
- 로그인을 각 기능에 붙이기 전까지 AI-07 API는 이 PC(127.0.0.1)에서 온 요청만 받는다.
