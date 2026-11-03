"""법령·업무 기준 관리 API (A-11 · A-12 · F-05). 주소: /api/standards/... · RADAR 운영자만. SQL v2.1 필요.

GET  /api/standards/jurisdiction          담당 부서 표 (87 + 88) — 어드민 '담당 부서 표' 화면 (목업 JURISDICTION 모양)
GET  /api/standards/changes?unseen=true   규정 변경 목록 (89) — 어드민 '규정 변경' 화면 (목업 ADMIN_REGULATIONS 모양)
POST /api/standards/changes/{id}/seen     규정 변경 확인 (seen_at · seen_by)
GET  /api/standards/drafts?limit=50       올린 담당 부서 표 수정안 목록 (62 '담당 부서 표') — 상태(승인 대기·승인·반려) +
                                          같은 표 줄에 걸린 규정 변경(89)의 원문 앞부분(before·after, 최대 500자) +
                                          basisQuery(근거 이름) → 화면에서 원문 전체는 GET /api/ai05/search?q=… 로 찾음 (10/28)
POST /api/standards/drafts                담당 부서 표 수정안 올리기 → 62 setting_version '제안' (승인은 I-07)
    {"jurId": "JUR-05", "problem": "가로등·보안등 문제", "from": "…", "to": "…", "basis": "성남시 사무위임 조례 별표 1"}

바꾸는 기록은 접근 기록(70)에 '설정 변경'으로 남긴다 (POL-022).
A-11·A-12 명령이 실패하면 운영 화면 실행 기록(AD-07)에서 '다시 실행'할 수 있다 (rerun_hooks, I-06).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core import access_audit as audit
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.standards.dept_draft import check_draft, parse_proposal_text, submit
from app.services.standards.repository import StandardsRepository, get_repository
from app.services.standards import rerun_hooks  # noqa: F401  서버가 켜질 때 A-11·A-12 '다시 실행'(I-06) 등록

router = APIRouter(prefix="/api/standards", tags=["법령·업무 기준 (A-11·A-12·F-05)"])
operator = require_roles("operator")


@router.get("/jurisdiction")
def jurisdiction(_u: dict = Depends(operator), repo: StandardsRepository = Depends(get_repository)):
    rows = repo.jurisdiction()
    for r in rows:
        r["depts"] = [{k: d.get(k) for k in ("gu_name", "condition_text", "dept_name", "org_level")} for d in r["depts"]]
    return {"jurisdiction": rows}


@router.get("/changes")
def changes(unseen: bool = False, limit: int = Query(200, ge=1, le=1000), _u: dict = Depends(operator),
            repo: StandardsRepository = Depends(get_repository)):
    out = []
    for c in repo.list_changes(unseen, limit):
        out.append({"id": c["standard_change_id"], "kind": c["change_kind"], "name": c["doc_name"],
                    "where": c.get("where_text"), "change": c["change_type"],
                    "date": c["effective_date"].isoformat() if c.get("effective_date") else None,
                    "before": c.get("before_text"), "after": c.get("after_text"),
                    "juris": [x for x in (c.get("related_jur") or "").split(",") if x],
                    "criteria": [x for x in (c.get("related_criteria") or "").split(",") if x],
                    "detected_at": c["detected_at"].isoformat(timespec="minutes") if c.get("detected_at") else None,
                    "seen": c.get("seen_at") is not None})
    return {"changes": out}


@router.post("/changes/{change_id}/seen")
def seen(change_id: int, request: Request, user: dict = Depends(operator),
         repo: StandardsRepository = Depends(get_repository)):
    if not repo.mark_seen(change_id, user["user_id"]):
        raise ApiError(404, "change_not_found", "규정 변경 기록을 찾을 수 없습니다")
    return {"ok": True}


class DraftBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    jur_id: str = Field(alias="jurId", max_length=20)
    problem: str = Field(max_length=200)
    from_: str = Field(alias="from", max_length=300)
    to: str = Field(max_length=300)
    basis: str = Field(max_length=200)
    label: str | None = Field(default=None, max_length=200)


@router.post("/drafts")
def submit_draft(body: DraftBody, request: Request, user: dict = Depends(operator)):
    draft = {"jur_id": body.jur_id, "problem": body.problem, "from": body.from_, "to": body.to, "basis": body.basis}
    try:
        check_draft(draft)
    except ValueError as e:
        raise ApiError(400, "invalid_draft", str(e)) from None
    sv_id = submit(draft, user["user_id"], body.label)
    audit.record(request, user, audit.SETTING_CHANGE, key=f"담당 부서 표 수정안 {body.jur_id}", reason="담당 부서 표 수정안 제안")
    return {"ok": True, "setting_version_id": sv_id, "status": "제안"}


STATUS_LABEL = {"제안": "승인 대기", "승인": "승인", "돌려보냄": "반려"}     # 화면 말 (DB 값은 그대로)


def _iso(v, spec="minutes"):
    return v.isoformat(timespec=spec) if hasattr(v, "hour") else (v.isoformat() if v else None)


@router.get("/drafts")
def drafts(limit: int = Query(50, ge=1, le=200), _u: dict = Depends(operator),
           repo: StandardsRepository = Depends(get_repository)):
    """올린 수정안 + 근거 원문 앞부분 (AD-11). 근거 원문 전체는 보관하지 않는다 — basisQuery로 AI-05 검색을 부르면 보유 원문에서 찾음."""
    out, cache = [], {}
    for d in repo.list_drafts(limit):
        p = parse_proposal_text(d.get("content_ref"))
        jur = p["jur_id"]
        if jur and jur not in cache:
            cache[jur] = [{"id": c["standard_change_id"], "kind": c["change_kind"], "name": c["doc_name"],
                           "where": c.get("where_text"), "change": c["change_type"],
                           "date": c["effective_date"].isoformat() if c.get("effective_date") else None,
                           "before": c.get("before_text"), "after": c.get("after_text")}
                          for c in repo.changes_for_jur(jur)]
        out.append({"id": d["setting_version_id"], "label": d.get("version_label"), "text": d.get("content_ref"),
                    "status": d.get("approval_status"), "status_label": STATUS_LABEL.get(d.get("approval_status"), d.get("approval_status")),
                    "proposed_at": _iso(d.get("proposed_at")), "decided_at": _iso(d.get("approved_at")),
                    "review_comment": d.get("review_comment"),
                    "jur_id": jur, "problem": p["problem"], "from": p["from"], "to": p["to"], "basis": p["basis"],
                    "basis_query": p["basis"], "changes": cache.get(jur, [])})
    return {"drafts": out}

# F-01 source-to-jurisdiction preview. Read-only; no assignment or approval.
# Register under the existing STANDARDS router; do not change app/main.py.
from typing import Any
from app.services.standards.f01_source_bridge import source_to_kinds, jurisdiction_candidates

class F01PreviewBody(BaseModel):
    gid: str = Field(min_length=1, max_length=100)
    source_table: str = Field(min_length=1, max_length=80)
    source_rows: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    gu: str | None = Field(default=None, max_length=100)


@router.post("/f01/preview")
def f01_preview(body: F01PreviewBody, _u: dict = Depends(operator),
                repo: StandardsRepository = Depends(get_repository)):
    """Source evidence supplied by caller -> advisory first department candidates.

    DB87 and DB88 are read via the existing repository. No DB writes.
    Caller-supplied rows are NOT independently verified against source tables.
    DB88 conditional rows are blocked unless separately verified; this endpoint
    deliberately does not accept a caller-controlled condition_verified flag.
    """
    try:
        candidates, unresolved = source_to_kinds(
            gid=body.gid, table=body.source_table, rows=body.source_rows
        )
    except ValueError as exc:
        raise ApiError(400, "invalid_f01_source", str(exc)) from None

    jurisdiction = repo.jurisdiction()
    rules = [
        {"jurisdiction_id": r["id"], "confirm_status": r.get("status"),
         "basis": r.get("basis")}
        for r in jurisdiction
    ]
    departments = [
        {"jurisdiction_id": r["id"], **d}
        for r in jurisdiction for d in r.get("depts") or []
    ]
    results = []
    for candidate in candidates:
        match = jurisdiction_candidates(candidate, rules, departments, gu=body.gu,
                                        condition_verified=False)
        results.append({"source_table": candidate.source_table,
                        "source_id": candidate.source_id,
                        "gid": candidate.gid,
                        "problem_kind": candidate.kind,
                        "evidence": candidate.evidence,
                        "classification_basis": candidate.basis,
                        **match})
    return {
        "status": "READ_ONLY_PREVIEW", "gid": body.gid,
        "source_provenance": "CALLER_SUPPLIED_NOT_DB_VERIFIED",
        "source_rows_received": len(body.source_rows),
        "results": results, "unresolved": unresolved,
        "department_finalized": False,
        "db_writes": 0,
    }


# F-01 additional verified-source path. Only source records read from the
# official database may use SOURCE_DB_VERIFIED. No caller-supplied row content.
from app.services.standards.f01_verified_source import load_verified_f01_row

class F01VerifiedSourceBody(BaseModel):
    gid: str = Field(min_length=1, max_length=100)
    source_table: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=120)
    gu: str | None = Field(default=None, max_length=100)


@router.post("/f01/preview/verified-source")
def f01_verified_source_preview(body: F01VerifiedSourceBody,
                                _u: dict = Depends(operator),
                                repo: StandardsRepository = Depends(get_repository)):
    """Read a single row from an allowlisted original source table, then
    classify and show advisory departments; never persist an assignment.
    The claimed `gu` is an unverified filter and cannot establish jurisdiction.
    """
    try:
        row = load_verified_f01_row(table=body.source_table, gid=body.gid,
                                    source_id=body.source_id)
        kinds, unresolved = source_to_kinds(gid=body.gid,
                                            table=body.source_table, rows=[row])
    except ValueError as exc:
        raise ApiError(400, "invalid_f01_source", str(exc)) from None
    jurisdiction = repo.jurisdiction()
    rules = [{"jurisdiction_id": r["id"], "confirm_status": r.get("status"),
              "basis": r.get("basis")} for r in jurisdiction]
    departments = [{"jurisdiction_id": r["id"], **d}
                   for r in jurisdiction for d in (r.get("depts") or [])]
    results = []
    for candidate in kinds:
        # A client-supplied gu must not be treated as independently checked.
        matched = jurisdiction_candidates(candidate, rules, departments,
                                           gu=None, condition_verified=False)
        results.append({"source_table": candidate.source_table,
                        "source_id": candidate.source_id,
                        "gid": candidate.gid, "problem_kind": candidate.kind,
                        "evidence": candidate.evidence,
                        "classification_basis": candidate.basis, **matched})
    return {"status": "READ_ONLY_PREVIEW", "gid": body.gid,
            "source_provenance": "SOURCE_DB_VERIFIED_ROW_ID_AND_GID",
            "source_rows_received": 1, "results": results,
            "unresolved": unresolved, "department_finalized": False,
            "db_writes": 0}
