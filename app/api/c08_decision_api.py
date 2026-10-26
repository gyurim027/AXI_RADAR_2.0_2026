"""C08 reviewer-authenticated row-level relevance decisions; NEVER bulk-promotes AI candidates.
Existing src_complaint and src_complaint_change only; no DDL, no 77/78 writes.
A verified review is a single human decision, not population confirmation.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.responses import ApiError
from app.api.c08_type_prereview_api import verified_operator
from app.services.c08.row_decision import record_decision, get_decision, review_queue, review_progress

router = APIRouter(prefix='/api/c08/decisions', tags=['C08 민원별 사람 검토'])

class ReviewRequest(BaseModel):
    complaint_id: str = Field(min_length=1, max_length=128)
    relevance: str
    reason: str = Field(min_length=8, max_length=255)
    expected_relevance: str | None = None

@router.post('')
def submit_review(body: ReviewRequest, actor: dict = Depends(verified_operator)):
    if body.relevance not in ('보행안전 관련', '비관련'):
        raise ApiError(422, 'invalid_decision', '보행안전 관련 또는 비관련을 선택하세요')
    return record_decision(body.complaint_id,body.relevance,body.reason,
                           actor['user_id'],body.expected_relevance)

@router.get('/{complaint_id}')
def read_decision(complaint_id: str, actor: dict = Depends(verified_operator)):
    return get_decision(complaint_id)


@router.get('/queue')
def pending_review_queue(limit: int = 25, offset: int = 0, gu: str | None = None,
                         actor: dict = Depends(verified_operator)):
    return review_queue(limit=limit, offset=offset, gu=gu)


@router.get('/progress')
def pending_review_progress(actor: dict = Depends(verified_operator)):
    return review_progress()
