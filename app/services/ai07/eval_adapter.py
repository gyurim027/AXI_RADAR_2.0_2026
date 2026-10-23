"""AI-07 평가용 어댑터 (W05-06 공통 평가 틀에 넣는 함수, 초안 — 진이님 코드 위치에 맞게 고쳐 주세요).

정답 목록(data/eval/ai07_cases.xlsx)의 '입력' 칸 JSON을 읽어
- schema_version이 ai07.e02로 시작하면 → E-02 근거 카드 explain_card(...)의 explanation (문항 001~012)
- 아니면 → 미평가 설명 explain(...)의 반환 문자열 (문항 013~020)
을 돌려준다. 설명문만 비교한다(입력 JSON은 비교하지 않음). 오류·빈 설명문은 평가 틀이 '틀림'으로 센다.
"""
from __future__ import annotations

import importlib
import json

# 진이님 모듈 위치 후보 (앞에서부터 찾음). 실제 위치가 다르면 여기만 고치면 된다
E02_MODULES = ("app.services.ai07.e02",)
UNEVALUATED_MODULES = ("app.services.ai07.engine_explainer",)


def _load(candidates, attr):
    for name in candidates:
        try:
            return getattr(importlib.import_module(name), attr)
        except ModuleNotFoundError as e:
            if e.name and name.startswith(e.name):
                continue
            raise
    raise ModuleNotFoundError(f"{attr} 함수를 찾을 수 없습니다: {', '.join(candidates)}")


def _text(out):
    if isinstance(out, dict):
        return out.get("explanation") or out.get("text")
    return out


def run(text: str):
    data = json.loads(text)
    if str(data.get("schema_version", "")).startswith("ai07.e02"):
        return _text(_load(E02_MODULES, "explain_card")(data))
    return _text(_load(UNEVALUATED_MODULES, "explain")(data))
