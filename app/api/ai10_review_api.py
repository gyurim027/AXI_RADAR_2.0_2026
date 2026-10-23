
"""AI-10 개발용 검토 API.

H-07 운영자 검토 요청에는 공통 인증 및 operator 역할을 적용한다.
개발용 쓰기는 AI10_DEV_API_ENABLED=1일 때만 허용한다.

현재 검토 결과는 개발용 JSON 저장소에 보관한다.
v2.1 운영 DB 저장·조회 연동은 별도 작업이다.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import require_roles
from app.services.ai10_action_proposal import compose_action_proposal
from app.services.ai10_operator_review import (
    STORE, decide, get_item, load_store, update_text,
)


class EditRequest(BaseModel):
    text: str = Field(min_length=1)


class DecisionRequest(BaseModel):
    note: str = Field(min_length=1)
    acknowledge_findings: bool = False
    evidence_source: str | None = None
    evidence_checked: bool = False


class ProposalRequest(BaseModel):
    confirmed_department: str | None = None
    confirmed_legal_basis: str | None = None


def create_router(store: Path = STORE) -> APIRouter:
    api = APIRouter(
        prefix="/api/ai10/reviews",
        tags=["AI-10 개발용 검토"],
    )
    operator_role = require_roles("operator")

    def protect_write():
        if os.getenv("AI10_DEV_API_ENABLED") != "1":
            raise HTTPException(
                status_code=403,
                detail="개발용 쓰기 API 비활성화",
            )

    def reviewer_id(user: dict) -> str:
        """개발용 JSON의 문자열 검토자 칸에 인증된 사용자 ID를 기록한다."""
        user_id = user.get("user_id")
        if type(user_id) is not int or user_id < 1:
            raise HTTPException(
                status_code=403,
                detail="운영자 식별번호를 확인할 수 없습니다.",
            )
        return str(user_id)

    def call(action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=str(exc)
            ) from exc
        except ValueError as exc:
            message = str(exc)
            if (
                "존재하지 않는 CK 번호" in message
                or "저장소가 없습니다" in message
            ):
                status = 404
            elif (
                "이미 승인" in message
                or "승인 문장" in message
                or "변경 사항이 없습니다" in message
                or "승인된 문장만" in message
            ):
                status = 409
            else:
                status = 400
            raise HTTPException(
                status_code=status, detail=message
            ) from exc

    def read_review(rule_id: str):
        data = call(load_store, store)
        return call(get_item, data, rule_id)

    @api.get("", dependencies=[Depends(operator_role)])
    def list_reviews():
        data = call(load_store, store)
        return [
            {
                "rule_id": rid,
                "review_status": item["review_status"],
                "approved": item["approved"],
                "finding_count": len(item["findings"]),
                "revision": item["revision"],
            }
            for rid, item in sorted(data["items"].items())
        ]

    @api.get("/approved/{rule_id}")
    def show_approved_template(rule_id: str):
        """H-06 연결: 승인된 문장 틀만 반환."""
        item = read_review(rule_id)
        if (
            item.get("review_status") != "approved"
            or item.get("approved") is not True
        ):
            raise HTTPException(
                status_code=404,
                detail="사용 가능한 승인 문장이 없습니다.",
            )
        template = item.get("edited_template")
        if not isinstance(template, str) or not template.strip():
            raise HTTPException(
                status_code=404,
                detail="사용 가능한 승인 문장이 없습니다.",
            )
        return {
            "rule_id": rule_id,
            "template": template,
            "revision": item["revision"],
            "approved_at": item["approved_at"],
        }

    @api.post("/proposals/{rule_id}")
    def compose_proposal(rule_id: str, payload: ProposalRequest):
        """H-06: 외부에서 확인한 부서·조문과 승인 문장을 결합."""
        result = call(
            compose_action_proposal,
            rule_id,
            confirmed_department=payload.confirmed_department,
            confirmed_legal_basis=payload.confirmed_legal_basis,
            store=store,
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="사용 가능한 승인 문장이 없습니다.",
            )
        return result

    @api.get(
        "/{rule_id}",
        dependencies=[Depends(operator_role)],
    )
    def show_review(rule_id: str):
        return read_review(rule_id)

    @api.put("/{rule_id}/text")
    def edit_review(
        rule_id: str,
        payload: EditRequest,
        user: dict = Depends(operator_role),
    ):
        protect_write()
        call(
            update_text,
            rule_id,
            payload.text,
            reviewer_id(user),
            store,
        )
        return read_review(rule_id)

    @api.post("/{rule_id}/approve")
    def approve_review(
        rule_id: str,
        payload: DecisionRequest,
        user: dict = Depends(operator_role),
    ):
        protect_write()
        call(
            decide,
            rule_id,
            reviewer_id(user),
            "approve",
            payload.note,
            payload.acknowledge_findings,
            store,
            evidence_source=payload.evidence_source or "",
            evidence_checked=payload.evidence_checked,
        )
        return read_review(rule_id)

    @api.post("/{rule_id}/reject")
    def reject_review(
        rule_id: str,
        payload: DecisionRequest,
        user: dict = Depends(operator_role),
    ):
        protect_write()
        call(
            decide,
            rule_id,
            reviewer_id(user),
            "reject",
            payload.note,
            False,
            store,
        )
        return read_review(rule_id)

    @api.post("/{rule_id}/revoke")
    def revoke_review(
        rule_id: str,
        payload: DecisionRequest,
        user: dict = Depends(operator_role),
    ):
        protect_write()
        call(
            decide,
            rule_id,
            reviewer_id(user),
            "revoke",
            payload.note,
            False,
            store,
        )
        return read_review(rule_id)

    return api


router = create_router()
