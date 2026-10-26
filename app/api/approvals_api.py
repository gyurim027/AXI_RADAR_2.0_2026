"""I-07. F-05의 /api/standards 경로를 덮어쓰지 않는 제안 검토 API."""
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.approvals.repository import ApprovalRepository, get_repository

router = APIRouter(prefix="/api/approvals", tags=["제안 승인·돌려보내기 (I-07)"])
reviewer = require_roles("city")


class ReviewBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    decision: Literal["승인", "돌려보냄"]
    review_comment: str | None = Field(default=None, alias="reviewComment", max_length=255)


@router.get("")
def proposals(status: Literal["제안", "승인", "돌려보냄"] = "제안",
              limit: int = Query(100, ge=1, le=500), user: dict = Depends(reviewer),
              repo: ApprovalRepository = Depends(get_repository)):
    return {"proposals": repo.list_proposals(status, limit)}


@router.get("/unapplied")
def unapplied_departments(user: dict = Depends(reviewer), repo: ApprovalRepository = Depends(get_repository)):
    return {"proposals": repo.pending_department()}


@router.get("/{proposal_id}")
def detail(proposal_id: int = Path(gt=0, le=9223372036854775807), user: dict = Depends(reviewer),
           repo: ApprovalRepository = Depends(get_repository)):
    return repo.get_proposal(proposal_id)


@router.post("/{proposal_id}/review")
def review(body: ReviewBody, request: Request, proposal_id: int = Path(gt=0, le=9223372036854775807),
           user: dict = Depends(reviewer), repo: ApprovalRepository = Depends(get_repository)):
    if body.decision == "돌려보냄" and not (body.review_comment or "").strip():
        raise ApiError(422, "review_comment_required", "돌려보내는 사유를 적어 주세요")
    return repo.decide(proposal_id, body.decision, body.review_comment, request, user)


@router.get("/{proposal_id}/preview")
def preview_department(proposal_id: int = Path(gt=0, le=9223372036854775807),
                       user: dict = Depends(reviewer), repo: ApprovalRepository = Depends(get_repository)):
    return repo.preview_department(proposal_id)


@router.post("/{proposal_id}/apply")
def retry_department(proposal_id: int = Path(gt=0, le=9223372036854775807),
                     user: dict = Depends(reviewer), repo: ApprovalRepository = Depends(get_repository)):
    return repo.retry_department(proposal_id, user)
