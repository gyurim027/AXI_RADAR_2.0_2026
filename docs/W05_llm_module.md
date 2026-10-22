# W05-05 공통 LLM 모듈 (초안 v0.1)

모든 AI 기능은 LLM을 `app/core/llm.py`의 `call_llm()` 하나로 부른다. 각 기능은 무엇을 물을지(프롬프트)만 만들고, 어느 모델로·내부/외부 어디로 보낼지, 보내도 되는지, 무엇을 기록할지는 모듈이 정한다. 담당: 규림 · 2026-10-21 · 기준: W05 공통 구조 v0.1(`docs/W05_common_structure.md`), 기능정의서 v0.5.3(POL-008·POL-021, ISS-017·ISS-032)

## 1. 파일

| 경로 | 넣는 것 |
|---|---|
| `app/core/llm.py` | `call_llm()`, 외부 전송 검사, 제공자 호출(Ollama·Gemini), 재시도, 로그 |
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

- 빠진 값은 `[defaults]`를 쓴다 (temperature 0, max_tokens 1024, timeout_s 60, max_retries 2, json_retries 1).
- 지금 들어 있는 작업은 LLM을 부르거나 붙이기로 한 세 곳이다: `ai03_refine`(위치 글자 다듬기), `ai07_explain`(설명문 다듬기), `ai10_draft`(조치 제안 문장 초안). AI-03·AI-10 값은 지금 각 코드와 같다.

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
  **무료 키로는 공개 자료나 가짜 문장만 보낸다.** 무료 서비스는 보낸 내용이 Google 제품 개선에 쓰이고 사람이 읽을 수 있다 (Gemini API 추가 약관).
- 시연·공용 서버: 팀 공용 유료 키 하나를 서버 `.env`에만 넣는다. 키는 저장소·채팅·문서에 올리지 않는다.
- 비용은 로그의 토큰 수로 확인한다.

## 10. 아직 없는 것

- 대량 처리 (동시 호출 수 제한, 중간에 끊긴 곳부터 이어 돌리기)
- 임베딩 호출
- 각 기능 코드를 `call_llm()`으로 바꾸기 (금요일 합칠 때)
