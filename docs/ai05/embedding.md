# AI-05 임베딩 검색 · 은경, 10/26

기준: 기능정의서 v0.5.3 '05_AI 기능 후보' AI-05 — "임베딩: 한국어 임베딩 모델, 내부 실행" · "대응표에 없는 유형만 검색한다. 찾은 원문 조각만 근거로 쓰고 그대로 인용한다."
공통 규칙: `docs/W05_llm_module.md` (규림) — AI 모델은 공통 LLM 모듈로만 부른다. 임베딩 호출은 10절 '아직 없는 것' → 규림님께 추가 요청.

## 무엇이 바뀌나
| | 전 | 후 |
|---|---|---|
| 대응표 경로 (문제 유형 → 조문) | 원문에서 그 조를 꺼냄 | 그대로 |
| 검색 경로 (대응표에 없을 때) | 낱말 검색(BM25)만 — 글자가 달라 못 찾음 (예: "인도 폭" ↔ "보도의 너비") | 낱말 순위 + 임베딩(뜻) 순위를 섞음(RRF) |
| 못 찾음 | 낱말이 충분히 겹치지 않으면 '보유 원문에서 못 찾음' | 낱말이 겹치거나, 뜻이 기준(sim_min)보다 가까울 때만 찾음. sim_min = 관계없는 질문 10개의 가장 높은 유사도 + 0.02 |
| 답 | 원문 조각 그대로 인용 | 그대로 (임베딩은 순위만 바꿈, 글을 만들지 않음) |

## 공통 모듈에 바라는 모양 (규림님께 요청)
```python
call_embed(task: str, texts: list[str], *, request_id: str | None = None) -> LlmResult
# ok=True  → data = [[숫자, ...], ...]  (texts와 같은 순서·같은 개수), model = 모델 이름
# ok=False → error_code (unknown_task / internal_unavailable / ...)
```
```toml
[tasks.ai05_embed]
# AI-05 법령 원문 조각·검색 질문 → 숫자 묶음. 공개 법령 원문만, 민원·개인정보 없음. 내부 모델만.
route = "internal"
model = "<공용 PC Ollama의 다국어 임베딩 모델 — 규림님이 정함>"
```
- 공통 모듈에 `call_embed`가 없거나, 작업이 없거나, Ollama가 꺼져 있으면 **낱말 검색만** 쓴다 (코드 수정 없이 등록되면 켜짐).
- 질문할 때 공용 PC가 꺼져 있으면 그 질문만 낱말 검색으로 답한다 (오류 없음).

## 공용 PC에서 만들고 비교하기
```powershell
uv run python -m scripts.ai05_build_embeddings              # 조각 약 3,400개 → data/ai05/embeddings.npy + 전후 비교
uv run python -m scripts.ai05_build_embeddings --compare    # 만든 파일로 비교만
```
- 비교: 색인 자체 평가(1등 정답 · 5등 안 정답 · 관계없는 질문 걸러냄)와 W05-06 20문항을 '낱말 검색만' / '낱말 + 임베딩'으로 각각 돌림. 자세한 결과는 `out/ai05/embed_compare_<날짜>.json`
- **기능정의서대로 임베딩을 쓰는 것이 기본이다.** 비교에서 임베딩 쪽 점수가 낱말 검색만보다 낮으면 아래 순서로 고친다.
  1. 다른 임베딩 모델로 바꿔 다시 비교한다 (규림님 `llm_tasks.toml` `[tasks.ai05_embed]`의 model만 바꾸고 `ai05_build_embeddings`를 다시 돌림)
  2. 섞는 방법을 조정한다: 임베딩 순위의 무게(`rag.LawIndex.EMB_W`), 섞을 후보 수(`POOL`), '못 찾음' 기준(`embed.SIM_MARGIN`) (AI-05 담당 은경)
  3. 그래도 낮으면 결과를 이 문서에 남기고 팀과 정한다. 잠깐 끄려면 `data/ai05/embeddings.npy`·`embeddings_meta.json`을 지우면 낱말 검색만으로 돌아간다 (비상용)
- `embeddings.*`는 저장소에 올리지 않는다(.gitignore). 조각(`chunks.jsonl`)이 바뀌면 지문이 달라져 옛 파일은 쓰지 않으니 다시 만든다.
- 지금 쓰는 방식은 `/api/ai05/health`의 '검색 방식' 칸: `낱말 + 임베딩 (모델)` / `낱말 검색만 (이유)`

## 확인한 것 / 못 한 것
- [x] 가짜 임베딩으로 시험 6개 (`tests/test_ai05_embed.py`): 글자가 달라도 뜻으로 찾음 · 관계없는 질문은 계속 못 찾음 · 호출 실패 시 낱말 검색 · 조각이 바뀐 옛 파일은 안 씀 · 공통 모듈 결과 모양
- [x] 낱말 검색만일 때 결과는 전과 같음 (20문항 17/20)
- [ ] 실제 모델 품질 — 규림님 `call_embed` 추가 뒤 공용 PC에서
