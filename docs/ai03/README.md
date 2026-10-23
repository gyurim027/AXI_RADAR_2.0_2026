# AI-03 위치 글자 다듬기 (A-07 좌표 맞추기 · C-06 민원 위치 찾기) — 세은

좌표가 빈 행의 위치 글자를 규칙·내부 자료 대조·브이월드로 찾고, 실패분만 LLM이 검색어를 다듬는다. **AI는 검색어만 만들고 좌표는 브이월드·성남시 공공데이터에서만** 가져온다. 검증을 통과한 것만 쓰고, 확신이 낮은 것('반영 보류')은 사람 확인 전에는 내지 않는다.

## 파일

| 경로 | 내용 |
|---|---|
| `app/services/ai03/rules.py` | 규칙 정리·분류 (꼬리말·약칭·도로 이름만·구간·성남 밖·위치 없음) |
| `app/services/ai03/internal_match.py` | 성남시 공공데이터 이름 대조 (신호기·바닥신호등·버스정류장) |
| `app/services/ai03/vworld.py` | 브이월드 주소·장소 검색 (캐시 `out/ai03/vworld_cache.json`) |
| `app/services/ai03/llm.py` | 검색어 다듬기 — 공통 LLM 모듈 `call_llm("ai03_refine", …)` |
| `app/services/ai03/validate.py` | 검증 (격자 안·구·동·도로 단서·이름·신호 지점 거리·도로명주소 번호) |
| `app/services/ai03/grid.py` | 좌표 → gid (명세서 7장: EPSG:5179 → 250m) |
| `app/services/ai03/pipeline.py` | `process()`(교차로) · `process_place()`(장소·민원) · `by_address()`(설치주소) |
| `app/services/ai03/eval_adapter.py` | 평가 어댑터 `run` / `run_status` / `run_accuracy` |
| `scripts/ai03_locate.py` | 배치 (parking · signal · police · complaint) |
| `data/ai03/` | 기준 자료 (공개 자료 가공): 격자, 이름 대조 2,211곳, 신호 지점, 도로 기준점·이름 |
| `data/eval/ai03_*.csv` | 정답 목록 (사람 검수 결과, 민원 제외) |
| `tests/test_ai03_rules.py` | 시험 (브이월드·LLM·DB 없이) |

## 실행

```powershell
uv sync --extra ai03
uv run python -m pytest tests/test_ai03_rules.py
uv run python -m scripts.ai03_locate parking --target 시도안함 --no-ai --start 0 --limit 7000
uv run python -m scripts.eval_run --name ai03 --cases data/eval/ai03_cases.csv --adapter app.services.ai03.eval_adapter:run
```

- 결과는 `out/ai03/`에만 (저장소에 올리지 않음). DB는 이 배치가 바꾸지 않는다 — 반영은 확인 뒤 따로.
- 브이월드 하루 호출 한도가 있어 큰 표는 `--start/--limit`로 나눠 돌린다. 한도에 걸리면 멈추고 이어서 돌릴 위치를 알려 준다.
- 캐시(`out/ai03/*_cache.json`)가 있으면 같은 결과가 다시 나온다. 다른 PC로 옮길 때는 캐시를 저장소 밖에서 복사한다.

## 원칙

좌표 빈 행만 채움 · AI는 검색어만 · 검증 통과만 · 도로 이름만이면 점 좌표를 만들지 않음(POL-018) · 외부 AI 전송 미확인 자료는 내부 모델만(POL-021, 공통 LLM 모듈이 강제) · 출처: 국토교통부 브이월드(사전 승낙), 성남시 공공데이터

## 결과 (10/23)

| 자료 | 대상 | 반영 |
|---|---|---|
| 경찰 보행신호 | 교차로 126곳 | 79곳 (119행) |
| 단속장소 | 21,506곳 | 7,023곳 (단속 35,280건) |
| 교통신호기 | 395곳 | 218곳 |
| 민원 위치 칸 | 428건 | 36건 |

평가(339건): 오연결률 6.1% (10건 모두 정답 칸 바로 옆 칸 — gid 기준이 사람 검수 250m보다 엄격) · 아님 100% · 못 찾음 100%

## 남은 것

- 기준 자료를 `data/ai03` CSV 대신 DB 표(01·41·50·55·35·18·45)에서 읽기
- DB 반영 스크립트 (dry-run → 한 거래로, 좌표 빈 행만)
- C-06 민원 본문 위치: AI-01 가린 요약 1년치 받은 뒤 (본문 처리 배치는 민원 자료라 결과를 저장소에 두지 않음)
