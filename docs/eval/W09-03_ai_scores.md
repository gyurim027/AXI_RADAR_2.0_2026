# AI 기능 평가 결과 모음 (대장 08 WBS W09-03 "핵심 AI 기능 평가 — 기능별 점수 기록") · 은경, 10/26

평가 틀: W05-06 `scripts.eval_run` (`app/services/evaluation/harness.py`) · 정답 목록: `data/eval/` (각 AI 담당자) · 자세한 결과 파일: 돌린 PC의 `out/eval/` (저장소에 올리지 않음)
기준: 기능정의서 v0.5.4 05_AI 기능 후보 — 각 AI의 '평가' 칸

## 지금 점수
| AI | 담당 | 정답 목록 | 언제·어디서 | 점수 |
|---|---|---|---|---|
| AI-03 민원 위치 | 세은 | `ai03_cases.csv` 339 | 10/26 19:40 세은 PC (VWORLD_KEY, 저장한 VWorld·AI 캐시) | **248/339 (73.2%)** · 잘못된 격자 연결 10 / 결과 낸 164 → **오연결률 6.1%** · 찾은 비율 163/244 (66.8%) · 아님 28/28 · 못 찾음 67/67 |
| | | `ai03_status_cases.csv` 311 | 같음 | 상태 230/311 (74.0%) — 틀린 81은 모두 '성공이어야 하는데 못 찾음' (위 찾은 비율의 놓친 81과 같은 문제) |
| | | `ai03_accuracy_cases.csv` 183 | 같음 | 좌표 정확도 112/183 (61.2%) — 결과 낸 112는 모두 맞음, 71은 좌표를 못 내서 정확도도 없음 |
| AI-05 법령 RAG | 은경 | `ai05_cases.csv` 20 | 10/26 은경 PC Ollama bge-m3 (낱말 + 임베딩, 조정 후) | **17/20** · 오연결률 16.7% · 색인 자체 평가 검색 5등 안 0.885 · 관계없는 질문 10/10 걸러냄 (`docs/ai05/embedding.md`) |
| AI-10 조치 제안 문장 | 대환 | `ai10_cases.csv` 14 (PR 중) | — | **아직** — 규칙 파일 `data/ai10_rules/ai10_generation_rules_v0.1.json`이 PR에 없어 다른 PC에서 14건 모두 오류 (대환님께 요청함) |
| AI-01 민원 정제 | 규림 | `ai01_relevance_cases.csv` 16 · `ai01_mask_cases.csv` 12 | — | **아직** (공용 PC Ollama exaone3.5:7.8b 필요) |
| AI-07 근거 문장 | 진이 | `ai07_cases.xlsx` | — | **아직** |

## 읽는 법 (모든 AI 공통)
- **맞음 비율**: 정답 목록 전체 중 맞힌 비율
- **오연결률** = 결과를 냈는데 틀린 수 ÷ 결과 낸 수 — 잘못 연결하는 위험. 못 찾은 것은 넣지 않음
- **찾은 비율** = 찾아야 하는 문제(같음·포함·N등 안) 중 결과를 낸 비율 — 놓치는 정도
- AI-03처럼 **잘못 연결(6.1%)보다 못 찾음이 많으면** 사람이 위치를 확인할 일이 남지만, 엉뚱한 격자 점수가 오르지는 않음 (기능정의서 AI-03: 못 찾으면 좌표를 붙이지 않음)
- **'못 찾음'을 글자로 돌려주는 어댑터**(AI-03 상태 평가)는 `--empty "못 찾음"`을 붙여 돌린다. 안 붙이면 놓친 것이 '오연결'로 세어져 오연결률이 26.0%처럼 크게 보인다 (10/26 평가 틀 고침)

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
