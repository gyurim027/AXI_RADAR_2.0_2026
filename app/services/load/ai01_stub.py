"""AI-01 가짜 함수 (AI-01 함수 약속 2·5장). 진짜 함수는 app/services/ai01/refine.py (규림 담당)가 같은 모양으로 만든다.

원문의 어떤 글자도 결과에 넣지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComplaintInput:
    complaint_id: str
    source_type: str
    title: str              # 원문, 저장 금지
    body: str               # 원문, 저장 금지
    report_type_raw: str | None


@dataclass
class Ai01Result:
    complaint_id: str
    status: str             # ok / mask_failed / error
    masked_summary: str | None
    relevance: str | None
    ped_type: str | None
    class_confidence: float | None
    class_reason: str | None
    model: str


def refine_complaints(items: list[ComplaintInput]) -> list[Ai01Result]:
    return [Ai01Result(i.complaint_id, "ok", "(가짜 요약) 민원 내용", "불명", None, 0.0, "가짜 결과(stub)", "stub") for i in items]
