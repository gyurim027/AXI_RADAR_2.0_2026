"""적재 7단계를 순서대로 묶는다 (명세서 3장).

1 올리기(출처·기간) → 형식 확인 → 2 민원ID → 3 칸 쌓기·규칙 가림 → 4 AI-01 → 5 좌표·격자 →
검사 → 신규/기존/갱신 + 80 → 7 84에 결과 한 줄.
원문(제목·본문)은 4단계가 끝나면 메모리에서 비운다. 파일은 디스크에 저장하지 않는다.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from app.services.load import dupes
from app.services.load.ai01_port import AI_COLS, HUMAN, METHOD_COL, AiSummary, apply_ai01
from app.services.load.checks import CheckReport, run_checks
from app.services.load.coords import Grid
from app.services.load.fields import build_record, parse_date
from app.services.load.ids import make_ids
from app.services.load.reader import LoadFileError, read_rows
from app.services.load.recurrence import mark_recurrence
from app.services.load.upsert import Counts, apply_records

log = logging.getLogger("radar.load")


@dataclass
class UploadMeta:
    data_name: str
    source: str
    ref_date: date
    period_start: date
    period_end: date
    is_official_raw: str = "가공본"           # 공식 배포판인지 모르면 가공본 (A-03)
    uploaded_by: int | None = None            # 로그인(I-01)이 붙기 전에는 NULL


@dataclass
class LoadResult:
    upload_id: int
    rows: int
    counts: Counts
    ai: AiSummary
    check: CheckReport
    remark: str
    warnings: list[str] = field(default_factory=list)


def validate_meta(meta: UploadMeta) -> None:
    """출처와 기간이 없는 파일은 올릴 수 없다 (C-09). 기간은 한 달(1일~말일)."""
    if not (meta.source or "").strip():
        raise LoadFileError("missing_source", "출처를 적어야 합니다.")
    if not (meta.data_name or "").strip():
        raise LoadFileError("missing_name", "자료 이름을 적어야 합니다.")
    s, e = meta.period_start, meta.period_end
    last = calendar.monthrange(s.year, s.month)[1]
    if s.day != 1 or (e.year, e.month, e.day) != (s.year, s.month, last):
        raise LoadFileError("invalid_period", "기간은 한 달(1일부터 말일까지)이어야 합니다.")


def run_load(data: bytes, file_name: str, meta: UploadMeta, store, refine: Callable | None = None,
             rerun_ai01: bool = False, request_id: str | None = None) -> LoadResult:
    """rerun_ai01=True: 이미 AI-01 결과가 있는 민원도 다시 돌린다 (모델을 바꿨을 때). 바뀐 값은 80에 'AI-01'로 남는다."""
    validate_meta(meta)
    upload_id = store.create_upload(meta, file_name[:200])
    store.commit()                                   # 실패해도 84 줄은 남긴다
    try:
        result = _process(data, file_name, meta, store, refine, upload_id, rerun_ai01, request_id)
        store.commit()
        return result
    except Exception as e:
        store.rollback()
        reason = e.message if isinstance(e, LoadFileError) else "서버 오류로 적재하지 못했습니다."
        store.finish_upload(upload_id, f"실패 ({reason})", None, None)
        store.commit()
        if not isinstance(e, LoadFileError):
            log.error("load failed upload_id=%s error=%s", upload_id, type(e).__name__)     # 예외 상세는 남기지 않는다 (ISS-032)
        raise


def _process(data: bytes, file_name: str, meta: UploadMeta, store, refine, upload_id: int, rerun_ai01: bool,
             request_id: str | None) -> LoadResult:
    rows = sorted(read_rows(data), key=lambda r: r.number)
    if not rows:
        raise LoadFileError("empty_file", "민원이 한 건도 없는 파일입니다.")
    outside = sum(1 for r in rows if not (parse_date(r.received) and meta.period_start.isoformat() <= parse_date(r.received) <= meta.period_end.isoformat()))
    if outside:
        raise LoadFileError("period_mismatch", f"민원등록일이 적은 기간 밖인 민원이 {outside}건 있습니다.")

    ids, _numbered = make_ids(rows)
    has_method = store.supports_class_method()
    ai_cols = AI_COLS + ((METHOD_COL,) if has_method else ())
    grid = Grid(store.grid_rows())
    marks = dupes.mark(rows)
    records = []
    for r, cid, (dup, rep) in zip(rows, ids, marks):
        rec = build_record(r, cid, meta.period_start.year, meta.period_start.month, grid)
        rec.update(dup_flag=dup, repeated_title=rep, masked_summary=None, relevance=None, ped_type=None,
                   class_confidence=None, class_reason=None)
        if has_method:
            rec[METHOD_COL] = None                    # 관련 여부를 정한 방법 (79에 칸이 있는 DB에서만)
        records.append(rec)

    # 4단계 AI-01: 새 민원과 아직 AI-01 결과가 없는 기존 민원에만 부른다 (건당 수 초가 걸려, 이미 채워진 것을 다시 돌리지 않음)
    existing = store.get_existing(ids)
    is_human = lambda old: old is not None and old.get(METHOD_COL) == HUMAN       # C-08에서 사람이 고친 관련 여부
    todo = [i for i, rec in enumerate(records)
            if not is_human(existing.get(rec["complaint_id"]))
            and (rerun_ai01 or rec["complaint_id"] not in existing or existing[rec["complaint_id"]].get("masked_summary") is None)]
    for i, rec in enumerate(records):
        old = existing.get(rec["complaint_id"])
        if old is not None and (is_human(old) or (old.get("masked_summary") is not None and not rerun_ai01)):
            for c in ai_cols:                          # 이미 채워진 값(사람이 고친 값은 재실행해도)은 그대로 두고 비교에서도 같게 본다
                rec[c] = old.get(c)
    ai = apply_ai01([rows[i] for i in todo], [records[i] for i in todo], refine, upload_id=upload_id, request_id=request_id)
    for r in rows:                                    # 4단계가 끝나면 원문을 메모리에서 버린다 (ISS-032)
        r.title = r.body = ""

    # C-10 재발 표시: AI-01이 보행_유형을 채운 뒤에 계산한다 (79에 칸이 있는 DB에서만)
    recur_cnt = None
    if store.supports_recurrence():
        recur_cnt = mark_recurrence(records, store.find_priors({r["gid"] for r in records if r["gid"]}))

    owners = store.receipt_owners([r["source_receipt_no"] for r in records if r["source_receipt_no"]])
    check = run_checks(records, meta.period_start, owners, existing)
    if not check.passed:
        raise LoadFileError("check_failed", "검사 실패: " + " · ".join(check.failures))

    period = f"{meta.period_start.isoformat()}~{meta.period_end.isoformat()}"
    counts = apply_records(store, records, existing, upload_id, file_name, period)
    counts.missing = store.count_missing(meta.period_start, meta.period_end, ids)
    rows_after = store.count_rows()

    warnings = []
    if ai.attempted and ai.backend == "stub":
        warnings.append("AI-01을 불러오지 못해 AI-01 칸을 채우지 않았습니다" if ai.unavailable
                        else "AI-01 함수가 아직 연결되지 않아 AI-01 칸을 채우지 않았습니다")
    elif ai.mask_failed or ai.error:
        warnings.append(f"AI-01: 가림 실패 {ai.mask_failed}건, 오류 {ai.error}건은 AI-01 칸을 비워 두었습니다")
    if recur_cnt is None:
        warnings.append("79에 재발 표시 칸이 없어 재발 표시를 건너뛰었어요 (SQL v2.x 필요)")
    if not has_method:
        warnings.append("79에 관련 여부 방법 칸(class_method)이 없어 방법을 저장하지 않았어요 (SQL v2.x 필요)")
    if check.top50_overlap is not None and check.top50_overlap < check.top50_total:
        warnings.append(f"낮음 포함/제외 상위 50칸이 달라요 ({check.top50_overlap}/{check.top50_total})")
    if check.low_heavy_cells:
        warnings.append(f"낮음이 몰린 칸 {check.low_heavy_cells}곳")
    remark = (f"신규 {counts.new} · 기존 {counts.existing} · 갱신 {counts.updated}(바뀜 칸 {counts.change_rows}) · "
              f"빠짐 {counts.missing} · 낮음 상위50 겹침 {check.top50_overlap}/{check.top50_total} · 낮음 몰린 칸 {check.low_heavy_cells}"
              + (f" · 재발 {recur_cnt}" if recur_cnt is not None else ""))
    store.finish_upload(upload_id, "통과", rows_after, remark)
    log.info("load ok upload_id=%s rows=%d new=%d updated=%d", upload_id, len(records), counts.new, counts.updated)
    return LoadResult(upload_id, len(records), counts, ai, check, remark, warnings)
