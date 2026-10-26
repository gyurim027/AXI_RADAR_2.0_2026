"""F-05 AI 추출 — 바뀐 업무분장·조례 문장에서 (업무, 담당 부서, 도로 종류)를 뽑는다 (기능정의서 F-05 "AI 후보 + 사람 승인", AI-05).

공통 LLM 모듈(app/core/llm.py, W05-05 규림)의 call_llm으로만 부른다. 작업 이름: f05_extract (llm_tasks.toml에 규림이 등록)
- 내부 모델만 쓴다 (업무분장·조례는 공개 자료지만 대장 06에 아직 없어 외부 전송 허용 목록에 없음, POL-021).
- 작업이 아직 등록되지 않았거나(unknown_task) Ollama가 꺼져 있으면(internal_unavailable) None을 돌려준다
  → dept_draft가 지금까지의 규칙 방식으로 수정안을 만든다. 등록되면 코드를 고치지 않아도 AI로 뽑는다.

AI가 지어낸 값은 쓰지 않는다 (기능정의서 AI-05 지킬 것):
- 업무(duty)·부서(dept)는 **입력 문장 안에 그대로 있는 글자만** 받는다. 없으면 그 항목을 버린다.
- 도로 종류는 아래 ROAD_TYPES 중 하나이고 문장에 그 말이 있을 때만 받는다.
- 결과는 수정안 '후보'일 뿐이다. 근거 문장은 원문 그대로 붙이고, 시 도로과 승인 전에는 표를 바꾸지 않는다.
"""
from __future__ import annotations

import re
from typing import Any

TASK = "f05_extract"
ROAD_TYPES = ("고속국도", "자동차전용도로", "국도", "국지도", "지방도", "특별시도", "광역시도", "시도", "구도", "군도",
              "도시고속화도로", "보도", "보행자전용도로", "자전거도로", "차도", "이면도로", "골목길")

SYSTEM = (
    "너는 성남시 업무분장·사무위임 조례 문장을 읽고 표로 옮기는 도우미다. 해석하거나 추측하지 않는다.\n"
    "입력 문장에서 (업무, 담당 부서, 도로 종류)를 찾아 JSON으로만 답한다.\n"
    "규칙: 1) duty와 dept는 입력 문장에 있는 글자를 그대로 복사한다. 2) 문장에 없는 부서·업무·법령 번호를 만들지 않는다. "
    "3) 도로 종류(road_type)는 문장에 나오는 말(예: 국도, 지방도, 시도, 구도, 보도, 자전거도로)만 쓰고, 없으면 null. "
    "4) 찾을 것이 없으면 {\"items\": []}.\n"
    "답 모양: {\"items\": [{\"duty\": \"…\", \"dept\": \"…\", \"road_type\": \"…\" 또는 null}]}"
)


def _norm(s: Any) -> str:
    return re.sub(r"[\s·ㆍ・]+", "", str(s or ""))


def verify(items: Any, source: str) -> list[dict]:
    """AI 답 중 입력 문장에 실제로 있는 값만 남긴다."""
    src = _norm(source)
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        duty, dept, road = (str(it.get(k) or "").strip() for k in ("duty", "dept", "road_type"))
        if not duty or _norm(duty) not in src:
            continue                                           # 문장에 없는 업무 = 지어낸 것 → 버림
        if dept and _norm(dept) not in src:
            dept = ""                                          # 문장에 없는 부서는 비움 (규칙 방식 값을 씀)
        if road and (road not in ROAD_TYPES or _norm(road) not in src):
            road = ""
        out.append({"duty": duty, "dept": dept or None, "road_type": road or None})
    return out


def extract(source: str, *, request_id: str | None = None, call=None) -> dict | None:
    """문장 하나 → {"items": [...], "model": "..."} · AI를 못 쓰면 None (규칙 방식으로)."""
    source = (source or "").strip()
    if not source:
        return None
    if call is None:
        from app.core.llm import call_llm as call
    res = call(TASK, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": source[:2000]}],
               data_ids=[], contains_raw=False, response_format="json", request_id=request_id)
    if not getattr(res, "ok", False):
        return None                                            # unknown_task · internal_unavailable · invalid_json …
    data = getattr(res, "data", None) or {}
    return {"items": verify(data.get("items") if isinstance(data, dict) else None, source),
            "model": getattr(res, "model", None)}
