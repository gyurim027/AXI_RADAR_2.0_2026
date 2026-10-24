"""AI-01 민원 정제: 민원 적재(W07-01) 4단계에서 부르는 함수.

    from app.services.ai01.refine import ComplaintInput, refine_complaints
    results = refine_complaints([ComplaintInput(complaint_id, source_type, title, body, report_type_raw), ...])

한 업로드 파일의 민원을 묶음으로 받아 같은 순서·같은 개수로 결과를 돌려준다.
- status ok: DB 79의 27 masked_summary, 31 relevance, 32 ped_type, 33 class_confidence, 34 class_reason에 쓴다
  class_method(관련 여부를 정한 방법: 규칙 / AI)는 79에 class_method 칸이 생기면 쓴다
- status mask_failed: 가림 검사를 통과하지 못함. class_reason만 '가림 실패', 나머지(class_method 포함)는 None (분류로 보내지 않음, C-03)
- status error: 모델 호출 실패 등. 적재는 이 민원의 AI-01 칸을 비워 두고 나중에 다시 돌린다
- ped_type(유형)은 유형 목록(ISS-016)이 정해질 때까지 None
- 원문(title·body)은 이 함수 안에서만 쓰고 결과·로그에 남기지 않는다 (ISS-032). 28 raw_pii_patterns는 적재 3단계가 채운다
- 긴 글은 요약과 관련 여부를 모델 한 번으로 받는다(judge). 한 묶음 안에서 가린 글이 같은 민원은 한 번만 처리하고 결과를 복사한다
- 실행 기록: app.core.job_run 의 '분류' 한 줄(건수·상태만)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.core.job_run import track
from app.services.ai01 import classify as cls
from app.services.ai01 import judge as jdg
from app.services.ai01 import masking, summarize as summ

MASK_FAILED_REASON = "가림 실패"
ONE_CALL = True          # 긴 글: 요약·관련 여부를 한 번에(True) / 요약 → 분류 두 번(False, 비교 시험용)
_SAME = re.compile(r"[\s\W_]+")


@dataclass
class ComplaintInput:
    complaint_id: str
    source_type: str
    title: str
    body: str
    report_type_raw: str | None = None


@dataclass
class Ai01Result:
    complaint_id: str
    status: str                        # ok / mask_failed / error
    masked_summary: str | None = None
    relevance: str | None = None
    ped_type: str | None = None
    class_confidence: float | None = None
    class_reason: str | None = None
    class_method: str | None = None     # 규칙 / AI. 실패면 None
    model: str = ""


def _model_tag() -> str:
    one = f"+{jdg.VERSION}" if ONE_CALL else ""
    return f"{masking.VERSION}+{summ.VERSION}+{cls.VERSION}{one}"


def decide(masked_text: str, report_type_raw: str | None = None, request_id: str | None = None):
    """가린 글 → (요약, 관련 여부, 신뢰도, 판단 근거, 정한 방법). 요약이 없으면 (None,)*5, 분류 실패면 요약만 채운다."""
    if report_type_raw:                                       # 신고 분류가 본문과 맞으면 모델 없이 끝낸다 (처리 시간)
        quick = cls.decide_without_model(report_type_raw, masked_text)
        if quick:
            summary = summ.rule_summary(cls.normalize_type(report_type_raw), masked_text)
            return (summary, *quick, cls.BY_RULE)
    if ONE_CALL and len(summ._clean(masked_text)) > summ.SHORT:
        judged = jdg.judge(masked_text, request_id=request_id)
        if judged is None:
            return (None,) * 5
        summary, _, *answer = judged
        rule = cls.by_rule(summary)                           # 규칙이 맞으면 규칙이 먼저다 (분류와 같은 순서)
        return (summary, *rule, cls.BY_RULE) if rule else (summary, *answer, cls.BY_AI)
    summary, _ = summ.summarize(masked_text, request_id=request_id)
    if not summary:
        return (None,) * 5
    decided = cls.classify(summary, report_type_raw, request_id=request_id, masked_text=masked_text)
    return (summary, *decided) if decided else (summary, None, None, None, None)


def refine_one(item: ComplaintInput, ner=None, request_id: str | None = None,
               drop: frozenset = frozenset(), seen: dict | None = None) -> Ai01Result:
    """seen: 한 묶음 안에서 같은 가린 글의 결과 (같은 글이면 모델을 다시 부르지 않고 복사한다)."""
    m = masking.mask(item.title, item.body, ner=ner, drop=drop)
    if not m.ok:
        return Ai01Result(item.complaint_id, "mask_failed", class_reason=MASK_FAILED_REASON, model=_model_tag())
    key = (cls.normalize_type(item.report_type_raw), _SAME.sub("", m.text))
    if seen is not None and key in seen:
        return replace(seen[key], complaint_id=item.complaint_id)
    summary, relevance, conf, reason, method = decide(m.text, item.report_type_raw, request_id)
    if not summary or relevance is None:
        return Ai01Result(item.complaint_id, "error", masked_summary=summary, model=_model_tag())
    r = Ai01Result(item.complaint_id, "ok", masked_summary=summary, relevance=relevance, ped_type=None,
                   class_confidence=conf, class_reason=reason, class_method=method, model=_model_tag())
    if seen is not None:
        seen[key] = r
    return r


def refine_complaints(items: list[ComplaintInput], *, upload_id=None, request_id: str | None = None,
                      ner=None) -> list[Ai01Result]:
    results = []
    with track("분류", f"민원 정제 AI-01 ({len(items)}건)", module="AI-01", ref_table="data_upload",
               ref_id=upload_id, request_id=request_id) as job:
        # 안내 줄 지우기는 안전신문고만 (안내 문구는 앱이 붙인다). 일반 민원은 같은 글을 여러 번 올린 집단 민원이 있어
        # 반복 줄이 실제 내용일 수 있으므로 지우지 않는다 (2026-10-23 적재 쪽 재확인: 일반 민원 25%의 본문이 지워짐).
        # 안전신문고: 저장소의 고정 안내 줄 + 이 묶음 안에서 반복되는 줄(전체·신고 분류별)
        spp = [i for i in items if masking.is_spp(i.source_type)]
        by_type = {}
        for i in spp:
            by_type.setdefault(cls.normalize_type(i.report_type_raw), []).append(i.body)
        drop_all = masking.spp_template_lines() | masking.repeated_lines([i.body for i in spp])
        drop_type = {k: masking.repeated_lines(v) for k, v in by_type.items()}
        seen = {}                                             # 같은 가린 글은 한 번만 (집단 민원, 2026-10-24)
        for item in items:
            try:
                drop = (drop_all | drop_type.get(cls.normalize_type(item.report_type_raw), frozenset())
                        if masking.is_spp(item.source_type) else frozenset())
                results.append(refine_one(item, ner=ner, request_id=request_id, drop=drop, seen=seen))
            except Exception:
                results.append(Ai01Result(item.complaint_id, "error", model=_model_tag()))   # 예외 글자에 원문이 섞일 수 있어 남기지 않음
        n = {s: sum(r.status == s for r in results) for s in ("ok", "mask_failed", "error")}
        copied = sum(r.status == "ok" for r in results) - len(seen)
        job.log(f"정제 {n['ok']}건(같은 글 복사 {copied}건), 가림 실패 {n['mask_failed']}건, 오류 {n['error']}건")
        job.rows(len(results))
        if n["mask_failed"] or n["error"]:
            job.warn(f"가림 실패 {n['mask_failed']}건, 오류 {n['error']}건은 AI-01 칸을 비워 둠")
    return results
