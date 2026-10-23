"""공통 LLM 호출 모듈 (W05-05, 초안 v0.1).

모든 AI 기능은 LLM을 이 모듈의 call_llm() 하나로 부른다. 각 기능은 "무엇을 물을지(프롬프트)"만 만들고,
어느 모델로·내부/외부 어디로 보낼지, 보내도 되는지, 무엇을 기록할지는 이 모듈이 정한다.

    from app.core.llm import call_llm

    result = call_llm(
        "ai03_refine",                                   # llm_tasks.toml의 작업 이름
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
        data_ids=["DAT-05"],                             # 프롬프트에 들어간 자료 (대장 06 데이터 ID)
        contains_raw=False,                              # 가리기 전 민원 원문이 들어 있으면 True
        response_format="json",                          # "text" 또는 "json"
        request_id=request.state.request_id,             # API에서 부를 때 (배치는 비워 둠)
    )
    if result.ok:
        use(result.data)                                 # json이면 data, text면 result.text
    else:
        handle(result.error_code)                        # 예외를 던지지 않고 실패 코드를 돌려준다

규칙
- 작업별 모델·경로는 app/core/llm_tasks.toml 한 곳에 둔다 (모델 미정, ISS-017).
- 기본은 내부 모델(Ollama). 외부(Gemini)는 작업 설정이 external이고 아래 조건이 모두 맞을 때만 보낸다.
  · contains_raw=False를 명시했다. 가리기 전 민원 원문은 외부로 보내지 않는다 (POL-008). 표시가 없으면 막는다.
  · data_ids가 비어 있지 않고, 모두 llm_tasks.toml [external_allowed]에 있다 (POL-021). 목록에 없거나 미확인이면 막는다.
- 막히면 외부로 보내지 않고 실패(external_not_allowed)로 돌려준다. 내부 모델로 몰래 바꾸지 않는다.
- Ollama가 꺼져 있으면 외부로 넘기지 않고 실패(internal_unavailable)로 돌려준다.
- 로그(radar.llm)에는 작업·경로·모델·성공 여부·실패 코드·시도 횟수·걸린 시간·토큰 수·request_id만 남긴다.
  프롬프트·답·오류 본문은 남기지 않는다 (ISS-032, W05 공통 구조 7장).
- 환경변수: OLLAMA_BASE_URL, LLM_DEFAULT_ROUTE, GEMINI_API_KEY, GEMINI_MODEL (.env.example)
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.core.config import get_settings

TASKS_PATH = Path(__file__).with_name("llm_tasks.toml")
ROUTES = ("internal", "external")

logger = logging.getLogger("radar.llm")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@dataclass(frozen=True)
class LlmResult:
    """call_llm()이 돌려주는 값. 실패해도 예외 대신 ok=False와 error_code를 준다."""
    ok: bool
    task: str
    route: str | None = None
    model: str | None = None                 # 실제로 쓴 모델 (결과를 다시 만들 때 필요)
    text: str | None = None
    data: Any = None                         # response_format="json"일 때 읽은 값
    error_code: str | None = None            # unknown_task / config_error / external_not_allowed / internal_unavailable
    #                                          / timeout / rate_limited / provider_error / invalid_json
    attempts: int = 0
    elapsed_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class TaskConfig:
    name: str
    route: str
    model: str
    temperature: float
    max_tokens: int
    timeout_s: float
    max_retries: int
    json_retries: int
    keep_alive: str = ""


class LlmError(Exception):
    """제공자 호출 실패. code만 쓰고 본문(입력 일부가 섞일 수 있음)은 버린다."""

    def __init__(self, code: str, retryable: bool = False):
        super().__init__(code)
        self.code, self.retryable = code, retryable


# ── 설정 ─────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_tasks(path: Path = TASKS_PATH) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _env(name: str, default: str = "") -> str:
    get_settings()                           # .env를 한 번 읽게 한다
    return os.environ.get(name, default).strip()


def task_config(task: str) -> TaskConfig | None:
    conf = load_tasks()
    raw = conf.get("tasks", {}).get(task)
    if raw is None:
        return None
    d = conf.get("defaults", {})
    route = (raw.get("route") or _env("LLM_DEFAULT_ROUTE", "internal")).lower()
    model = raw.get("model") or ""
    if route == "external" and not model:
        model = _env("GEMINI_MODEL")
    return TaskConfig(
        name=task, route=route, model=model,
        temperature=float(raw.get("temperature", d.get("temperature", 0))),
        max_tokens=int(raw.get("max_tokens", d.get("max_tokens", 1024))),
        timeout_s=float(raw.get("timeout_s", d.get("timeout_s", 60))),
        max_retries=int(raw.get("max_retries", d.get("max_retries", 2))),
        json_retries=int(raw.get("json_retries", d.get("json_retries", 1))),
        keep_alive=str(raw.get("keep_alive", d.get("keep_alive", ""))),
    )


def external_allowed(data_ids: Iterable[str], contains_raw: bool | None) -> bool:
    """외부로 보내도 되는지. 표시가 없거나 모르면 막는 쪽이 기본이다."""
    if contains_raw is not False:
        return False
    ids = [i for i in data_ids if i]
    allowed = set(load_tasks().get("external_allowed", {}).get("data_ids", []))
    return bool(ids) and all(i in allowed for i in ids)


# ── 제공자 ───────────────────────────────────────────

def _call_ollama(cfg: TaskConfig, messages: list[dict], want_json: bool) -> tuple[str, int | None, int | None]:
    base = _env("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    body = {"model": cfg.model, "messages": messages, "stream": False,
            "options": {"temperature": cfg.temperature, "num_predict": cfg.max_tokens}}
    if want_json:
        body["format"] = "json"
    if cfg.keep_alive:                       # 모델을 올려 둔 채로 둘 시간 (다시 올리는 지연 막기)
        body["keep_alive"] = cfg.keep_alive
    req = urllib.request.Request(base + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:                  # 모델을 받지 않았거나 이름이 틀림
            raise LlmError("config_error") from None
        raise LlmError("provider_error", retryable=exc.code >= 500) from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise LlmError("timeout", retryable=True) from None
        raise LlmError("internal_unavailable") from None          # Ollama가 꺼져 있음
    except (socket.timeout, TimeoutError):
        raise LlmError("timeout", retryable=True) from None
    except (ValueError, OSError):
        raise LlmError("provider_error") from None
    text = (out.get("message") or {}).get("content") or ""
    return text, out.get("prompt_eval_count"), out.get("eval_count")


def _call_gemini(cfg: TaskConfig, messages: list[dict], want_json: bool) -> tuple[str, int | None, int | None]:
    key = _env("GEMINI_API_KEY")
    if not key or not cfg.model:
        raise LlmError("config_error")
    from google import genai
    from google.genai import errors, types

    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or None
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                              parts=[types.Part(text=m["content"])])
                for m in messages if m["role"] != "system"]
    config = types.GenerateContentConfig(
        temperature=cfg.temperature, max_output_tokens=cfg.max_tokens, system_instruction=system,
        response_mime_type="application/json" if want_json else None,
        http_options=types.HttpOptions(timeout=int(cfg.timeout_s * 1000)),
    )
    client = genai.Client(api_key=key)
    try:
        resp = client.models.generate_content(model=cfg.model, contents=contents, config=config)
    except errors.APIError as exc:
        code = getattr(exc, "code", 0) or 0
        if code == 429:
            raise LlmError("rate_limited", retryable=True) from None
        raise LlmError("provider_error", retryable=code >= 500) from None
    except (TimeoutError, socket.timeout):
        raise LlmError("timeout", retryable=True) from None
    except Exception:                        # 오류 본문에 입력 일부가 섞일 수 있어 종류만 남긴다
        raise LlmError("provider_error") from None
    finally:
        try:
            client.close()
        except Exception:
            pass
    usage = getattr(resp, "usage_metadata", None)
    return (resp.text or "",
            getattr(usage, "prompt_token_count", None), getattr(usage, "candidates_token_count", None))


PROVIDERS = {"internal": _call_ollama, "external": _call_gemini}


# ── 호출 ─────────────────────────────────────────────

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _parse_json(text: str) -> Any:
    return json.loads(_FENCE.sub("", text.strip()))


def _check_messages(messages: list[dict]) -> None:
    if not messages or not all(isinstance(m, dict) and m.get("role") in ("system", "user", "assistant")
                               and isinstance(m.get("content"), str) for m in messages):
        raise ValueError("messages는 role(system/user/assistant)과 content(글자)를 가진 dict 목록이어야 합니다")


def call_llm(task: str, messages: list[dict], *, data_ids: Iterable[str] = (), contains_raw: bool | None = None,
             response_format: str = "text", request_id: str | None = None) -> LlmResult:
    """LLM을 부른다. 자세한 규칙은 이 파일 맨 위 설명."""
    _check_messages(messages)
    if response_format not in ("text", "json"):
        raise ValueError("response_format은 'text' 또는 'json'입니다")
    data_ids = list(data_ids)
    start = time.perf_counter()

    def done(**kw) -> LlmResult:
        r = LlmResult(task=task, elapsed_ms=round((time.perf_counter() - start) * 1000, 1), **kw)
        _log(r, request_id)
        return r

    cfg = task_config(task)
    if cfg is None:
        return done(ok=False, error_code="unknown_task")
    if cfg.route not in ROUTES or not cfg.model:
        return done(ok=False, route=cfg.route, error_code="config_error")
    if cfg.route == "external" and not external_allowed(data_ids, contains_raw):
        return done(ok=False, route=cfg.route, model=cfg.model, error_code="external_not_allowed")

    call = PROVIDERS[cfg.route]
    want_json = response_format == "json"
    attempts, json_left = 0, cfg.json_retries
    tokens_in = tokens_out = None
    while True:
        attempts += 1
        try:
            text, t_in, t_out = call(cfg, messages, want_json)
        except LlmError as exc:
            if exc.retryable and attempts <= cfg.max_retries:
                time.sleep(min(2 ** (attempts - 1), 8))           # 1초, 2초, 4초 … 간격을 늘려 다시
                continue
            return done(ok=False, route=cfg.route, model=cfg.model, error_code=exc.code, attempts=attempts,
                        input_tokens=tokens_in, output_tokens=tokens_out)
        if t_in is not None:                                     # JSON 형식이 틀려 다시 부르면 토큰을 더한다
            tokens_in = (tokens_in or 0) + t_in
        if t_out is not None:
            tokens_out = (tokens_out or 0) + t_out
        if not want_json:
            return done(ok=True, route=cfg.route, model=cfg.model, text=text, attempts=attempts,
                        input_tokens=tokens_in, output_tokens=tokens_out)
        try:
            data = _parse_json(text)
        except ValueError:
            if json_left > 0:
                json_left -= 1
                continue
            return done(ok=False, route=cfg.route, model=cfg.model, error_code="invalid_json", attempts=attempts,
                        input_tokens=tokens_in, output_tokens=tokens_out)
        return done(ok=True, route=cfg.route, model=cfg.model, text=text, data=data, attempts=attempts,
                    input_tokens=tokens_in, output_tokens=tokens_out)


def _log(r: LlmResult, request_id: str | None) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "request_id": request_id, "module": "llm", "task": r.task, "route": r.route, "model": r.model,
        "ok": r.ok, "error_code": r.error_code, "attempts": r.attempts, "duration_ms": r.elapsed_ms,
        "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
    }, ensure_ascii=False))
