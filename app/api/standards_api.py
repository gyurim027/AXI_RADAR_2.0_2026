"""법령·업무 기준 관리 API (A-11 · A-12 · F-05). 주소: /api/standards/... · RADAR 운영자만. SQL v2.1 필요.

GET  /api/standards/jurisdiction          담당 부서 표 (87 + 88) — 어드민 '담당 부서 표' 화면 (목업 JURISDICTION 모양)
GET  /api/standards/changes?unseen=true   규정 변경 목록 (89) — 어드민 '규정 변경' 화면 (목업 ADMIN_REGULATIONS 모양)
POST /api/standards/changes/{id}/seen     규정 변경 확인 (seen_at · seen_by)
POST /api/standards/drafts                담당 부서 표 수정안 올리기 → 62 setting_version '제안' (승인은 I-07)
    {"jurId": "JUR-05", "problem": "가로등·보안등 문제", "from": "…", "to": "…", "basis": "성남시 사무위임 조례 별표 1"}

바꾸는 기록은 접근 기록(70)에 '설정 변경'으로 남긴다 (POL-022).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core import access_audit as audit
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.standards.dept_draft import check_draft, submit
from app.services.standards.repository import StandardsRepository, get_repository

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
