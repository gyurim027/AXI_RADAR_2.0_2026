"""AI-01 요약과 관련 여부를 한 번에 (7·11단계를 모델 호출 한 번으로).

기능정의서 05 AI-01 ② "AI가 관련 여부와 유형을 한 번에 판단한다"에 맞춘다. 긴 가린 글(200자 초과)만 여기로 온다.
- 요약 검사는 summarize.check를 그대로 쓴다 (지어낸 장소 → 가린 글 앞부분, 개인정보 꼴 → 다시 가림)
- 관련 여부 기준·근거 형식은 classify와 같다. 규칙 2개(classify.by_rule)는 부른 쪽(refine)이 요약에 다시 대어 본다
- 유형(ped_type)은 유형 목록(ISS-016)이 정해지면 같은 답에 칸을 더한다
"""
from __future__ import annotations

import json

from app.core.llm import call_llm
from app.services.ai01 import classify as cls
from app.services.ai01 import summarize as summ

VERSION = "judge-1"

SYSTEM = summ.SYSTEM.split("답은 JSON")[0] + """
그다음 같은 민원이 '보행안전 관련'인지 정한다. 기준은 아래와 같다.
""" + cls.SYSTEM.split("\n", 1)[1].split("답은 JSON")[0] + """
답은 JSON 하나로만 한다: {"summary": "요약 문장", "relevance": "관련|비관련|불명", "confidence": 0~1 숫자, "reason": "묶음: 설명"}"""

# 지어낸 예시 (classify 예시에서 골라 요약 칸을 붙임. 정답 표본과 겹치지 않음)
EXAMPLES = [(q, {"summary": q, **a}) for q, a in (cls.EXAMPLES[i] for i in (0, 1, 4, 6, 8))]


def judge(masked_text: str, request_id: str | None = None):
    """(요약, 요약 검사에 걸린 것, 관련 여부, 신뢰도, 판단 근거). 모델 호출이 실패하면 None."""
    msgs = [{"role": "system", "content": SYSTEM}]
    for q, a in EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps(a, ensure_ascii=False)}]
    msgs.append({"role": "user", "content": masked_text[:summ.MAX_INPUT]})
    r = call_llm("ai01_judge", msgs, contains_raw=False, response_format="json", request_id=request_id)
    if not r.ok or not isinstance(r.data, dict):
        return None
    summary, hits = summ.check(str(r.data.get("summary", "")).strip(), masked_text)
    if not summary:
        return None
    return (summary, hits, *cls.read_answer(r.data))
