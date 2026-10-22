"""적재 4단계 AI-01 가림·분류 자리 (명세서 3·6장, AI-01 함수 약속).

- app/services/ai01/refine.py 가 있으면 그것을, 없으면 가짜 함수(stub)를 부른다.
- 원문(제목·본문)은 메모리로만 넘기고, 로그에는 건수만 남긴다.
- 27·31~34칸에는 status가 ok이고 model이 stub이 아닌 결과만 쓴다 (가짜 값이 DB에 들어가지 않게).
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Sequence

from app.services.load.ai01_stub import Ai01Result, ComplaintInput, refine_complaints as stub_refine
from app.services.load.reader import RawRow

log = logging.getLogger("radar.load")
AI_COLS = ("masked_summary", "relevance", "ped_type", "class_confidence", "class_reason")


def default_refine() -> Callable:
    try:
        from app.services.ai01.refine import refine_complaints
        return refine_complaints
    except ModuleNotFoundError as e:
        if e.name in ("app.services.ai01", "app.services.ai01.refine"):
            return stub_refine
        raise


@dataclass
class AiSummary:
    ok: int = 0
    mask_failed: int = 0
    error: int = 0
    stub: int = 0
    models: set = field(default_factory=set)


def apply_ai01(rows: Sequence[RawRow], records: Sequence[dict], refine: Callable | None = None) -> AiSummary:
    refine = refine or default_refine()
    items = [ComplaintInput(rec["complaint_id"], rec["source_type"], r.title, r.body, rec["report_type_raw"])
             for r, rec in zip(rows, records)]
    summary = AiSummary()
    try:
        results: list[Ai01Result] = list(refine(items))
    except Exception:                                   # 모델 호출 실패: 그 파일의 AI-01 칸만 비우고 적재는 계속
        log.warning("ai01 call failed (items=%d)", len(items))
        summary.error = len(items)
        return summary
    finally:
        items.clear()
    if len(results) != len(records) or any(res.complaint_id != rec["complaint_id"] for res, rec in zip(results, records)):
        log.warning("ai01 result shape mismatch")
        summary.error = len(records)
        return summary
    for res, rec in zip(results, records):
        if res.status == "ok":
            summary.ok += 1
            summary.models.add(res.model)
            if res.model == "stub":
                summary.stub += 1
                continue
            for c in AI_COLS:
                rec[c] = getattr(res, c)
        elif res.status == "mask_failed":
            summary.mask_failed += 1                    # 가림 실패: 분류로 보내지 않고 요약·분류 칸은 비움
            rec["class_reason"] = "가림 실패"
        else:
            summary.error += 1
    log.info("ai01 done ok=%d mask_failed=%d error=%d stub=%d", summary.ok, summary.mask_failed, summary.error, summary.stub)
    return summary
