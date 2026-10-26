# W05-05 공통 LLM 모듈 (초안 v0.1)

모든 AI 기능은 LLM을 `app/core/llm.py`의 `call_llm()`으로 부른다. 글을 숫자 묶음으로 바꾸는 임베딩은 같은 파일의 `call_embed()`로 부른다. 각 기능은 무엇을 물을지(프롬프트)만 만들고, 어느 모델로·내부/외부 어디로 보낼지, 보내도 되는지, 무엇을 기록할지는 모듈이 정한다. 담당: 규림 · 2026-10-21 · 기준: W05 공통 구조 v0.1(`docs/W05_common_structure.md`), 기능정의서 v0.5.3(POL-008·POL-021, ISS-017·ISS-032)

## 1. 파일

| 경로 | 넣는 것 |
|---|---|
| `app/core/llm.py` | `call_llm()`, `call_embed()`, 외부 전송 검사, 제공자 호출(Ollama·Gemini), 재시도, 로그 |
| `app/core/llm_tasks.toml` | 작업별 모델·경로·온도·길이·시간 제한, 외부 허용 자료 목록 |
| `tests/test_core_llm.py` | 가짜 응답으로 도는 시험 (실제 모델·키 없이) |

새 패키지는 없다. Ollama는 Python 표준 라이브러리로, Gemini는 기본 묶음의 `google-genai`로 부른다.

## 2. 부르는 법

```python
from app.core.llm import call_llm

result = call_llm(
    "ai03_refine",                                   # llm_tasks.toml의 작업 이름
    [{"role": "system", "content": "규칙…"}, {"role": "user", "content": "판교로256번길 …"}],
    data_ids=["DAT-05"],                             # 프롬프트에 들어간 자료 (대장 06 데이터 ID)
    contains_raw=False,                              # 가리기 전 민원 원문이 들어 있으면 True
    response_format="json",                          # "text" 또는 "json"
    request_id=request.state.request_id,             # API에서 부를 때. 배치는 비워 둔다
)
if result.ok:
    data = result.data                               # json이면 data, text면 result.text
else:
    print(result.error_code)                         # 예외를 던지지 않고 실패 코드를 돌려준다
```

돌려주는 값(`LlmResult`): `ok`, `task`, `route`, `model`(실제로 쓴 모델), `text`, `data`, `error_code`, `attempts`, `elapsed_ms`, `input_tokens`, `output_tokens`

- `messages`의 role은 `system` / `user` / `assistant`만 쓴다.
- `model`을 결과와 같이 저장해 두면 어떤 모델로 만든 결과인지 나중에 알 수 있다.

### 임베딩 부르기

글을 숫자 묶음으로 바꿀 때는 `call_embed()`를 쓴다. 내부 모델(Ollama)만 쓰고, 외부로는 보내지 않는다.

```python
from app.core.llm import call_embed

result = call_embed("ai05_embed", ["보도의 너비", "인도 폭"], request_id=None)
if result.ok:
    vectors = result.data                            # 글과 같은 순서·같은 개수의 숫자 목록
    model = result.model                             # 어떤 모델로 만들었는지 같이 저장한다
else:
    print(result.error_code)
```

- 돌려주는 값은 `call_llm()`과 같은 `LlmResult`다. `text`는 비어 있고, `input_tokens`만 채워진다.
- `texts`는 비어 있지 않은 글 목록이어야 한다. 빈 목록이나 빈 글을 넣으면 `ValueError`다.
- 공용 PC가 한 번에 하나씩 처리하므로 한 번에 32개 안팎으로 나눠 부른다.
- 가려야 하는 글(민원 원문 등)은 넣지 않는다. 지금 쓰는 곳은 공개 법령 원문 조각과 검색 질문뿐이다.

## 3. 외부 전송 규칙

기본은 내부 모델(Ollama)이다. 작업 설정이 `external`이어도 아래 두 조건이 **모두** 맞을 때만 외부(Gemini)로 보낸다.

1. `contains_raw=False`를 명시했다. 가리기 전 민원 원문은 외부로 보내지 않는다 (POL-008). 표시를 빼면 막는다.
2. `data_ids`가 비어 있지 않고, 모두 `llm_tasks.toml`의 `[external_allowed]`에 있다 (POL-021). 목록에 없거나 미확인인 자료가 하나라도 있으면 막는다.

막히면 외부로 보내지 않고 `external_not_allowed`를 돌려준다. 내부 모델로 몰래 바꾸지도 않는다.
**지금 허용 목록은 비어 있다.** 그래서 외부 작업은 모두 막힌다. 대장 06 '외부 AI 전송' 칸이 채워지면 목록에 넣는다.

## 4. 실패 코드

| 코드 | 뜻 | 다시 부름 |
|---|---|---|
| `unknown_task` | `llm_tasks.toml`에 없는 작업 이름 | - |
| `config_error` | 모델·키가 비었거나, Ollama에 그 모델이 없음 | - |
| `external_not_allowed` | 3장 조건이 안 맞아 외부로 안 보냄 | - |
| `internal_unavailable` | Ollama가 꺼져 있음 (외부로 넘기지 않음) | - |
| `timeout` | 시간 초과 | 최대 `max_retries`번 (1초, 2초, 4초 간격) |
| `rate_limited` | 외부 API 속도 제한 | 위와 같음 |
| `provider_error` | 그 밖의 제공자 오류 | 서버 오류(5xx)일 때만 |
| `invalid_json` | JSON으로 답하게 했는데 형식이 틀림 | 최대 `json_retries`번 |

`call_embed()`도 같은 코드를 쓴다. 외부 경로로 정한 작업은 `config_error`다. 숫자 묶음 개수나 모양이 글과 맞지 않으면 `provider_error`로 돌려주고 다시 부르지 않는다.

오류 본문에는 입력 일부가 섞일 수 있어 코드만 남기고 본문은 버린다.

## 5. 설정

환경변수(`.env`, `.env.example` 참고)

| 이름 | 쓰는 곳 |
|---|---|
| `OLLAMA_BASE_URL` | 내부 모델 주소 (기본 `http://localhost:11434`) |
| `LLM_DEFAULT_ROUTE` | 작업에 route가 없을 때 쓸 경로 (기본 `internal`) |
| `GEMINI_API_KEY` | 외부 모델 키 |
| `GEMINI_MODEL` | model이 비어 있는 외부 작업이 쓸 모델 (지금 AI-10 값) |

작업별 설정(`app/core/llm_tasks.toml`)

```toml
[tasks.ai03_refine]
route = "internal"          # internal / external
model = "exaone3.5:7.8b"
temperature = 0
max_tokens = 300
```

- 빠진 값은 `[defaults]`를 쓴다 (temperature 0, max_tokens 1024, timeout_s 120, keep_alive "30m", max_retries 2, json_retries 1).
- `think`: 생각하기 모델(qwen3 등)만 작업 줄에 `think = false`로 쓴다. 생각 글을 먼저 내 느리고 JSON이 깨지는 것을 막는다. 다른 모델 작업에는 쓰지 않는다(빼면 보내지 않음).
- `timeout_s`에는 공용 PC에서 차례를 기다리는 시간도 들어간다. `keep_alive`는 Ollama가 모델을 올려 둔 채로 둘 시간이다(비우면 Ollama 기본 5분).
- 지금 들어 있는 작업은 아홉 개다: `ai01_judge`(민원 긴 글의 요약과 관련 여부를 한 번에, 비교용), `ai01_summarize`(민원 가린 요약), `ai01_classify`(보행안전 관련 여부), `ai01_type`(관련 민원의 유형), `ai03_refine`(위치 글자 다듬기), `ai05_embed`(법령 원문 조각·검색 질문을 숫자 묶음으로, 임베딩), `ai07_explain`(설명문 다듬기), `ai10_draft`(조치 제안 문장 초안), `f05_extract`(바뀐 업무분장·조례 문장에서 업무·담당 부서·도로 종류 뽑기).
- 문장을 만드는 내부 작업은 모두 `exaone3.5:7.8b` 하나를 쓴다. 임베딩 작업(`ai05_embed`)만 `bge-m3`를 쓰고, `call_llm()`이 아니라 `call_embed()`로 부른다.
- `ai05_embed`는 `temperature`와 `max_tokens`를 쓰지 않는다. `f05_extract`의 결과는 수정안 후보로만 쓰고, 승인 전에는 담당 부서 표를 바꾸지 않는다.

## 6. 작업 더하기·바꾸기

- LLM을 새로 쓰게 되면 **PR 설명에** 작업 이름, 모델, 내부/외부, 들어가는 자료 ID를 적는다. `llm_tasks.toml`은 공통 파일이라 규림이 넣는다 (W05 공통 구조 8장).
- 모델을 바꿀 때도 이 파일의 `model` 한 줄만 고친다. 코드는 고치지 않는다.
- 각자 직접 부르던 코드(예: `generate_content`, `openai` 호출)는 금요일 합칠 때 `call_llm()`으로 바꾼다. 프롬프트·결과 검사·캐시는 각 기능에 그대로 둔다.

## 7. 로그

호출마다 JSON 한 줄(로거 `radar.llm`): `ts · request_id · module · task · route · model · ok · error_code · attempts · duration_ms · input_tokens · output_tokens`
프롬프트·답·오류 본문은 남기지 않는다 (ISS-032). `request_id`는 공통 요청 로그와 같은 값을 넘겨 이어 붙인다.

## 8. 시험

```powershell
uv run python -m pytest tests/test_core_llm.py      # 실제 모델·키 없이 돈다
```

실제 호출을 확인하려면 Ollama를 켜고 모델을 받은 뒤(`ollama pull exaone3.5:7.8b`) 부른다. 로그에 `"ok": true`가 찍히면 된다.

## 9. 키·모델 쓰는 법

- 각자 시험: Ollama는 각자 PC에 설치하고 `llm_tasks.toml`과 같은 모델을 받는다. Gemini 키는 각자 받아 `.env`에 넣는다.
- 팀 공용 PC: Ollama를 공용 PC 한 대에서 돌리고 같은 네트워크에서 함께 쓸 수 있다.
  - 쓰는 사람: 공용 PC 주소를 팀 채널에서 받아 `.env`에 `OLLAMA_BASE_URL=http://<공용 PC 주소>:11434`로 넣는다. 주소는 저장소·문서에 쓰지 않는다. 같은 네트워크 밖에서는 닿지 않는다(`internal_unavailable`)
  - 공용 PC 설정: `OLLAMA_HOST=0.0.0.0`(다른 PC에서 받기), 방화벽 11434 포트 열기, `OLLAMA_NUM_PARALLEL=1`(한 번에 하나씩 처리, 나머지는 차례를 기다림), `OLLAMA_MAX_LOADED_MODELS=1`(모델 하나만 올림). 설정을 바꾸면 Ollama를 다시 켠다
  - 임베딩 모델은 공용 PC에서 `ollama pull bge-m3`로 받는다(약 1.2GB, 라이선스 MIT, 숫자 묶음 길이 1024).
  - 공용 PC로 보내는 글은 가린 글이다. 가리기 전 원문을 다루는 모델(AI-01 이름 찾기)은 각자 PC에서 돈다
  - `OLLAMA_MAX_LOADED_MODELS=1`이면 임베딩 모델과 문장 모델을 번갈아 부를 때마다 모델을 바꿔 올려 느려진다. 둘을 함께 쓰려면 이 값을 2로 올려야 한다. 올려도 되는지(메모리)는 공용 PC 담당이 정한다
  - 대량 작업(AI-03 일괄, AI-01 월 적재)은 시연 시간과 겹치지 않게 돌린다
  **무료 키로는 공개 자료나 가짜 문장만 보낸다.** 무료 서비스는 보낸 내용이 Google 제품 개선에 쓰이고 사람이 읽을 수 있다 (Gemini API 추가 약관).
- 시연·공용 서버: 팀 공용 유료 키 하나를 서버 `.env`에만 넣는다. 키는 저장소·채팅·문서에 올리지 않는다.
- 비용은 로그의 토큰 수로 확인한다.

## 10. 아직 없는 것

- 대량 처리 (동시 호출 수 제한, 중간에 끊긴 곳부터 이어 돌리기)
- 각 기능 코드를 `call_llm()`으로 바꾸기 (금요일 합칠 때)
