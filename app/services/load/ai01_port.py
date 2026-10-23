"""적재 4단계 AI-01 가림·분류 자리 (명세서 3·6장, AI-01 함수 약속).

- app/services/ai01/refine.py 가 있으면 그것을, 없으면(또는 불러오지 못하면) 가짜 함수(stub)를 부른다.
- 원문(제목·본문)은 메모리로만 넘기고, 로그에는 건수만 남긴다.
- 27·31~34칸에는 status가 ok이고 model이 stub이 아닌 결과만 쓴다 (가짜 값이 DB에 들어가지 않게).
- 가린 요약에 개인정보 꼴이 남은 민원은 그 민원만 AI-01 칸을 비우고 '가림 실패'로 둔다 (파일 전체를 되돌리지 않음).
"""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Callable, Sequence

from app.services.load.ai01_stub import ComplaintInput as StubInput, refine_complaints as stub_refine
from app.services.load.masking import has_pii
from app.services.load.reader import RawRow

log = logging.getLogger("radar.load")
AI_COLS = ("masked_summary", "relevance", "ped_type", "class_confidence", "class_reason")
METHOD_COL = "class_method"                              # 관련 여부를 정한 방법: 규칙 / AI (사람은 C-08이 씀). 79에 칸이 있을 때만 레코드에 들어옴
METHODS = ("규칙", "AI")
HUMAN = "사람"
MASK_FAILED_REASON = "가림 실패"
_MISSING = ("app.services.ai01", "app.services.ai01.refine")


@dataclass
class Backend:
    refine: Callable
    input_cls: type
    kind: str                       # ai01 = 진짜 함수 · stub = 가짜 함수 · custom = 시험 등에서 직접 넘긴 함수
    unavailable: str | None = None  # 진짜 함수가 있는데 불러오지 못했을 때 그 이유(예외 종류·모듈 이름만)


def resolve_backend(refine: Callable | None = None) -> Backend:
    if refine is not None:
        return Backend(refine, StubInput, "custom")
    try:
        from app.services.ai01.refine import ComplaintInput, refine_complaints
        return Backend(refine_complaints, ComplaintInput, "ai01")
    except ModuleNotFoundError as e:
        if e.name in _MISSING:                           # AI-01이 아직 합쳐지지 않은 브랜치
            return Backend(stub_refine, StubInput, "stub")
        reason = e.name or "ModuleNotFoundError"
    except ImportError as e:
        reason = type(e).__name__
    log.warning("ai01 불러오기 실패: %s (가짜 함수 사용)", reason)         # 원문과 무관한 모듈 이름·예외 종류만
    return Backend(stub_refine, StubInput, "stub", unavailable=reason)


@dataclass
class AiSummary:
    ok: int = 0
    mask_failed: int = 0
    error: int = 0
    stub: int = 0
    attempted: int = 0                                   # AI-01에 보낸 민원 수
    backend: str = "custom"
    unavailable: str | None = None
    models: set = field(default_factory=set)


def _call(fn: Callable, items: list, upload_id, request_id):
    """upload_id·request_id를 받는 함수에만 넘긴다 (진짜 함수는 받고, 가짜·시험용 한 줄 함수는 안 받음)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(items)
    var_kw = any(p.kind is p.VAR_KEYWORD for p in params.values())
    kw = {}
    if upload_id is not None and ("upload_id" in params or var_kw):
        kw["upload_id"] = upload_id
    if request_id is not None and ("request_id" in params or var_kw):
        kw["request_id"] = request_id
    return fn(items, **kw)


def apply_ai01(rows: Sequence[RawRow], records: Sequence[dict], refine: Callable | None = None, *,
               upload_id=None, request_id: str | None = None) -> AiSummary:
    backend = resolve_backend(refine)
    summary = AiSummary(backend=backend.kind, unavailable=backend.unavailable)
    if not records:                                      # 보낼 민원이 없으면 부르지 않는다 (실행 기록도 남기지 않음)
        return summary
    summary.attempted = len(records)
    items = [backend.input_cls(rec["complaint_id"], rec["source_type"], r.title, r.body, rec["report_type_raw"])
             for r, rec in zip(rows, records)]
    try:
        results = list(_call(backend.refine, items, upload_id, request_id))
    except Exception:                                    # 모델 호출 실패: 그 파일의 AI-01 칸만 비우고 적재는 계속
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
            if METHOD_COL in rec:                        # 방법은 AI-01이 실제 결정 경로를 직접 돌려준 값만 쓴다 (근거 문구·신뢰도로 추측하지 않음)
                method = getattr(res, METHOD_COL, None)
                rec[METHOD_COL] = method if method in METHODS else None
            if has_pii(rec["masked_summary"]):           # 요약에 개인정보 꼴이 남음: 이 민원만 쓰지 않는다
                for c in AI_COLS:
                    rec[c] = None
                if METHOD_COL in rec:
                    rec[METHOD_COL] = None
                rec["class_reason"] = MASK_FAILED_REASON
                summary.ok -= 1
                summary.mask_failed += 1
        elif res.status == "mask_failed":
            summary.mask_failed += 1                     # 가림 실패: 분류로 보내지 않고 요약·분류 칸은 비움
            rec["class_reason"] = MASK_FAILED_REASON
        else:
            summary.error += 1
    log.info("ai01 done ok=%d mask_failed=%d error=%d stub=%d", summary.ok, summary.mask_failed, summary.error, summary.stub)
    return summary
