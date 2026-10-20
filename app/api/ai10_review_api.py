"""AI-10 개발용 검토 API. 운영 인증/DB 연동 전용이 아님.

app.main에서 app.include_router(router)를 추가해야 활성화됩니다.
쓰기 요청은 AI10_DEV_API_ENABLED=1에서만 허용됩니다.
"""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ai10_action_proposal import compose_action_proposal

from app.services.ai10_operator_review import (
    STORE, decide, get_item, load_store, update_text,
)


class EditRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    text: str = Field(min_length=1)


class DecisionRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    note: str = Field(min_length=1)
    acknowledge_findings: bool = False
    evidence_source: str | None = None
    evidence_checked: bool = False


class ProposalRequest(BaseModel):
    confirmed_department: str | None = None
    confirmed_legal_basis: str | None = None


def create_router(store: Path = STORE) -> APIRouter:
    api = APIRouter(prefix="/api/ai10/reviews", tags=["AI-10 개발용 검토"])

    def protect_write():
        if os.getenv("AI10_DEV_API_ENABLED") != "1":
            raise HTTPException(status_code=403, detail="개발용 쓰기 API 비활성화")

    def call(action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            message = str(exc)
            if "존재하지 않는 CK 번호" in message or "저장소가 없습니다" in message:
                status = 404
            elif "이미 승인" in message or "승인 문장" in message or "변경 사항이 없습니다" in message or "승인된 문장만" in message:
                status = 409
            else:
                status = 400
            raise HTTPException(status_code=status, detail=message) from exc

    @api.get("")
    def list_reviews():
        data = call(load_store, store)
        return [{
            "rule_id": rid,
            "review_status": item["review_status"],
            "approved": item["approved"],
            "finding_count": len(item["findings"]),
            "revision": item["revision"],
        } for rid, item in sorted(data["items"].items())]

    @api.get("/approved/{rule_id}")
    def show_approved_template(rule_id: str):
        """H-06 연동 전용: 승인된 문장 틀만 반환. 후보별 CK 판단은 하지 않음."""
        data = call(load_store, store)
        item = call(get_item, data, rule_id)
        if item.get("review_status") != "approved" or item.get("approved") is not True:
            raise HTTPException(status_code=404, detail="사용 가능한 승인 문장이 없습니다.")
        template = item.get("edited_template")
        if not isinstance(template, str) or not template.strip():
            raise HTTPException(status_code=404, detail="사용 가능한 승인 문장이 없습니다.")
        return {
            "rule_id": rule_id,
            "template": template,
            "revision": item["revision"],
            "approved_at": item["approved_at"],
        }

    @api.post("/proposals/{rule_id}")
    def compose_proposal(rule_id: str, payload: ProposalRequest):
        """H-06 독립 연결: 외부에서 확인한 부서·조문과 승인 문장만 결합.

        후보 선정/CK 자동매핑/법령 추론은 하지 않음. 저장소 쓰기 없음.
        """
        result = call(
            compose_action_proposal, rule_id,
            confirmed_department=payload.confirmed_department,
            confirmed_legal_basis=payload.confirmed_legal_basis,
            store=store,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="사용 가능한 승인 문장이 없습니다.")
        return result

    @api.get("/{rule_id}")
    def show_review(rule_id: str):
        data = call(load_store, store)
        return call(get_item, data, rule_id)

    @api.put("/{rule_id}/text")
    def edit_review(rule_id: str, payload: EditRequest):
        protect_write()
        call(update_text, rule_id, payload.text, payload.reviewer, store)
        return show_review(rule_id)

    @api.post("/{rule_id}/approve")
    def approve_review(rule_id: str, payload: DecisionRequest):
        protect_write()
        call(decide, rule_id, payload.reviewer, "approve", payload.note,
             payload.acknowledge_findings, store,
             evidence_source=payload.evidence_source or '',
             evidence_checked=payload.evidence_checked)
        return show_review(rule_id)

    @api.post("/{rule_id}/reject")
    def reject_review(rule_id: str, payload: DecisionRequest):
        protect_write()
        call(decide, rule_id, payload.reviewer, "reject", payload.note, False, store)
        return show_review(rule_id)

    @api.post("/{rule_id}/revoke")
    def revoke_review(rule_id: str, payload: DecisionRequest):
        protect_write()
        call(decide, rule_id, payload.reviewer, "revoke", payload.note, False, store)
        return show_review(rule_id)

    return api


router = create_router()
