# RADAR 2.0 — AI-05 법령 근거 찾기 (법령 RAG)

보유 법령·지침 원문에서 조문을 찾아 **원문 그대로** 인용합니다. 법 해석·위반 판단은 하지 않습니다.
근거 조문 후보는 운영자가 원문과 대조해 확정합니다(기능정의서 AD-13). 이 API는 DB에 쓰지 않습니다.

## 기능

| 주소 | 기능정의서 | 하는 일 |
|---|---|---|
| `GET /api/ai05/related?problem_type=T18` | E-04 관련 기준·조문 붙이기 | ① 대응표(지금은 57 criterion '대응표 대신') → ② 원문 검색 → ③ `보유 원문에서 못 찾음` |
| `GET /api/ai05/action-basis/CK-09` | H-07 근거 조문 후보 (AI-10 연결) | 81 action_template 한 줄의 근거 조문 후보. 확정된 `basis_article`(근거 조문)이 있으면 그것부터 (SQL v2 영문 컬럼) |
| `GET /api/ai05/search?q=보도 유효폭` | (개발·어드민 확인용) | 질문 → 원문 조각 |
| `GET /api/ai05/health` | | 색인 크기, 조치 제안 표를 DB/파일 중 어디서 읽었는지 |

결과 한 줄: `cite`(인용 표시) · `quote`(원문 그대로) · `status`(시행 중 / 시행 전 / 참고 자료(법령 아님)) · `effective`(시행일) · `future_version`(시행 전 개정판이 있으면) · `doc_type`.

## 폴더

| 경로 | 내용 |
|---|---|
| `app/api/ai05_law_api.py` | 라우터 (`prefix="/api/ai05"`) |
| `app/services/ai05/` | 본체: `rag.py`(색인·검색) · `service.py`(세 기능) · `extract.py`·`chunk.py`(원문 → 조각) · `evaluate.py`(평가) |
| `data/ai05/` | 색인과 데이터. **서버가 켜질 때 꼭 필요** (`law_index.pkl`, `criterion.json`, `action_table.json`). 공개 법령·지침으로 만든 파일만 있음 (민원·수치지형도 없음) |
| `scripts/ai05_build_index.py` | 색인 다시 만들기 |
| `tests/test_ai05_law.py` | 시험 23개 + 평가 4개 + API 4개 |

## 공통 서버에서 (W05-03)

공통 서버에 이미 붙어 있다 (`app/main.py`의 `ROUTERS`). DB는 공통 `app/core/db.py`로 읽고, 패키지는 루트 `pyproject.toml`에 들어 있다.

## 실행·시험 (저장소 루트, PowerShell)

```powershell
uv run uvicorn app.main:app --port 8000        # 공통 서버 켜기 → http://localhost:8000/docs
uv run python -m tests.test_ai05_law           # AI-05 시험 (끝에 '모두 통과')
```

공용 DB의 81 action_template을 읽으려면 루트 `.env`에 `RADAR_DB_*`를 채우고 켭니다 (`.env.example` 참고). 없으면 `data/ai05/action_table.json`(= 대장 05_03)을 읽습니다.
`/api/ai05/health`의 `조치 제안 표`가 `DB (…)`로 나오면 연결된 것입니다.

## 색인 다시 만들기

```powershell
uv run python -m scripts.ai05_build_index --from-chunks                 # data/ai05/chunks.jsonl로 색인만
uv run python -m scripts.ai05_build_index <법령 원문 폴더> 2026-10-21    # 원문부터 전부 (법령 개정 때)
```
원문 폴더는 저장소에 올리지 않습니다. pdf는 poppler의 `pdftotext`가 필요합니다.

## 아직 정해지지 않은 것

- 유형-조문 대응표(W02-03·W04-19)와 E-04에 넣을 문제 유형(CK / JUR / 화면 유형)이 정해지면 `problem_type`이 바뀝니다.
- 화면 조문 탭(`ArticlesTab.jsx`)은 `{id, name, effective, pending, body}`를 기대합니다. 연결할 때 `cite→name`, `quote→body`, `status=='시행 전'→pending`으로 맞춥니다.
- ~~평가 기준 질문 20개가 정해지지 않아 법령색인으로 대신 평가했습니다~~ → 10/23 기능정의서 기준 20문항(`data/eval/ai05_cases.csv`)으로 공통 평가 틀(W05-06)에서 평가: 16/20.
- 법령 색인 원문 대조(W04-19, 은경): `uv run python -m scripts.ai05_check_criterion` → `docs/ai05/criterion_check.csv`. 결과와 더 받아야 할 원문은 `docs/ai05/W04-19_criterion_check.md`.
- 임베딩 검색은 코드만 있고 시험하지 않았습니다.
