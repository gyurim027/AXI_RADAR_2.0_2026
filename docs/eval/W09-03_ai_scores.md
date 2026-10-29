# AI 기능 평가 결과 모음 (대장 08 WBS W09-03 "핵심 AI 기능 평가 — 기능별 점수 기록") · 은경, 10/29

평가 틀: W05-06 `scripts.eval_run` (`app/services/evaluation/harness.py`) · 정답 목록: `data/eval/` (각 AI 담당자) · 자세한 결과 파일: 돌린 PC의 `out/eval/` (저장소에 올리지 않음)
기준: 기능정의서 v0.5.4 05_AI 기능 후보 — 각 AI의 '평가' 칸

## 지금 점수
| AI | 담당 | 정답 목록 | 언제·어디서 | 점수 |
|---|---|---|---|---|
| AI-03 민원 위치 | 세은 | `ai03_cases.csv` 339 | 10/26 19:40 세은 PC (VWORLD_KEY, 저장한 VWorld·AI 캐시) | **248/339 (73.2%)** · 잘못된 격자 연결 10 / 결과 낸 164 → **오연결률 6.1%** · 찾은 비율 163/244 (66.8%) · 아님 28/28 · 못 찾음 67/67 |
| | | `ai03_status_cases.csv` 311 | 10/28 21:16 세은 PC, develop 528091b, `--empty "못 찾음"` | 상태 230/311 (74.0%) · 결과 낸 230 중 틀림 0 → **오연결률 0.0%** · 찾은 비율 230/311 — 틀린 81은 모두 '성공이어야 하는데 못 찾음'(st-ok). 진짜 오연결 없음 |
| | | `ai03_accuracy_cases.csv` 183 | 같음 | 좌표 정확도 112/183 (61.2%) — 결과 낸 112는 모두 맞음, 71은 좌표를 못 내서 정확도도 없음 |
| AI-05 법령 RAG | 은경 | `ai05_cases.csv` 20 | 10/26 은경 PC Ollama bge-m3 (낱말 + 임베딩, 조정 후) | **17/20** · 오연결률 16.7% · 색인 자체 평가 검색 5등 안 0.885 · 관계없는 질문 10/10 걸러냄 (`docs/ai05/embedding.md`) |
| AI-10 조치 제안 문장 | 대환 | `ai10_cases.csv` 14 | 10/28 14:20 은경 PC, 최신 develop (공통 LLM 모듈 ai10_draft → 내부 Ollama exaone3.5:7.8b) | **13/14 (92.9%)** · 오연결률 7.1% · 포함 6/7 · 안 들어감 7/7 (금지 표현 0) — 틀린 1: AI10-009 '현장 확인' 빠짐. LLM이라 돌릴 때마다 조금 다를 수 있음 |
| AI-01 민원 정제 | 규림 | `ai01_relevance_cases.csv` 16 · `ai01_mask_cases.csv` 12 | 10/27 규림 PC (Ollama exaone3.5:7.8b, 흔한 낱말 목록 656줄 지정) | **관련 여부 16/16 (100%)** · 오연결 0 · **가림 12/12 (100%)** · 안 들어감 11/11 · 포함 1/1 — 이 정답 목록 조건에서 오류가 없었다는 뜻이며 전체 자료 성능을 보장하지는 않음. 흔한 낱말 목록·결과 파일은 규림 PC에만 있음 |
| AI-07 근거 문장 (문장 틀) | 진이 | `ai07_cases.xlsx` 20 | 10/27 14:20 은경 PC, 최신 develop (LLM 안 부름) | **20/20 (100%)** · 오연결률 0.0% · 포함 14/14 · 안 들어감 6/6 — LLM 미호출 문장 틀 평가. 001~012 `app.services.ai07.e02.explain_card`, 013~020 `app.services.ai07.engine_explainer.explain` (진이 안내의 `run_ai07_unevaluated.explain`과 같은 함수) |
| AI-07 근거 문장 (E-03 다듬기) | 진이 | 공통 DB 실제 후보 5건 (`e03_real_db_final_5.csv`) | 10/29 진이 PC, 내부 Ollama(exaone3.5:7.8b) | Ollama 호출 5/5 · 수정문 수용 **0/5** · 원문 복원 5/5 · 전부 `unsupported_change`로 거부(예: 점수 자릿수 변경 79.6422→79.642, "실행 1" 표현 누락 4/5건) · 공통 DB 변경 없음(`db_written=False`) — 실제 DB 설명문에 기존 보수 검사 규칙을 적용한 평가이며, 실제 DB용 E-03 운영 기능 통합 완료를 의미하지는 않음 |

## 읽는 법 (모든 AI 공통)
- **맞음 비율**: 정답 목록 전체 중 맞힌 비율
- **오연결률** = 결과를 냈는데 틀린 수 ÷ 결과 낸 수 — 잘못 연결하는 위험. 못 찾은 것은 넣지 않음
- **찾은 비율** = 찾아야 하는 문제(같음·포함·N등 안) 중 결과를 낸 비율 — 놓치는 정도
- AI-03처럼 **잘못 연결(6.1%)보다 못 찾음이 많으면** 사람이 위치를 확인할 일이 남지만, 엉뚱한 격자 점수가 오르지는 않음 (기능정의서 AI-03: 못 찾으면 좌표를 붙이지 않음)
- **'못 찾음'을 글자로 돌려주는 어댑터**(AI-03 상태 평가)는 `--empty "못 찾음"`을 붙여 돌린다. 안 붙이면 놓친 것이 '오연결'로 세어져 오연결률이 26.0%처럼 크게 보인다 (10/26 평가 틀 고침)
- E-03 다듬기는 다른 행과 달리 정답 목록 대비 정확도가 아니라, **허용 안 된 변경(수치·누락 등)을 걸러내는지**를 보는 평가임 — "수정문 수용 0/5"는 실패가 아니라 보수 규칙이 의도대로 작동했다는 뜻

## 다시 돌리는 명령 (저장소 루트)
```powershell
uv run python -m scripts.eval_run --name ai03 --cases data/eval/ai03_cases.csv --adapter app.services.ai03.eval_adapter:run
uv run python -m scripts.eval_run --name ai03_status --cases data/eval/ai03_status_cases.csv --adapter app.services.ai03.eval_adapter:run_status --empty "못 찾음"
uv run python -m scripts.eval_run --name ai03_accuracy --cases data/eval/ai03_accuracy_cases.csv --adapter app.services.ai03.eval_adapter:run_accuracy
uv run python -m scripts.eval_run --name ai05 --cases data/eval/ai05_cases.csv --adapter app.services.ai05.eval_adapter:run
uv run python -m scripts.eval_run --name ai01_relevance --cases data/eval/ai01_relevance_cases.csv --adapter app.services.ai01.eval_adapter:run
uv run python -m scripts.eval_run --name ai01_mask --cases data/eval/ai01_mask_cases.csv --adapter app.services.ai01.eval_adapter:run_mask
uv run python -m scripts.eval_run --name ai07 --cases data/eval/ai07_cases.xlsx --adapter app.services.ai07.eval_adapter:run
uv run python -m scripts.eval_run --name ai10 --cases data/eval/ai10_cases.csv --adapter "app.services.AI-10.eval_adapter:run_text"
```
- AI-01·AI-07·AI-10 명령의 정답 목록과 어댑터 짝은 각 담당자가 맞는지 확인해 주세요 (은경은 파일 이름으로 짝을 지음)
- 정답 목록과 결과 파일에는 민원 원문·개인정보를 넣지 않는다 (ISS-032)
