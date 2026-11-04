"""Authenticated D-10 create route. Register explicitly after schema and team approval.

No development in-memory round IDs; never issues an official scoring authorization.
"""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.d10_run_creation import RunCreation, D10RunBlocked, create_d10_run

router = APIRouter(prefix='/api/d10/rounds', tags=['D-10 회차 생성'])
operator = require_roles('operator')

class D10CreateRequest(BaseModel):
    build_id: str = Field(min_length=1, max_length=255)
    rule_version: str = Field(min_length=1, max_length=255)
    period_start: date
    period_end: date
    weight_setting_version_id: int = Field(gt=1)
    threshold_setting_version_id: int = Field(gt=1)
    priority_condition_setting_version_id: int = Field(gt=1)
    note: str = Field(default='D10_CREATED_AWAITING_SCORING', max_length=100)

@router.post('', status_code=201)
def create_round(data: D10CreateRequest, user: dict = Depends(operator)) -> dict:
    # Auth is mandatory; a valid operator session is not scoring approval.
    # Create is explicitly initiated by the authorized operator's POST request.
    if not isinstance(user, dict) or not user.get('user_id'):
        raise ApiError(403, 'operator_identity_required', '관리자 신원을 확인할 수 없습니다')
    try:
        return create_d10_run(RunCreation(**data.model_dump()), explicit_creation_approval=True)
    except D10RunBlocked as exc:
        # Never treat incomplete deployment or unapproved policies as success.
        raise ApiError(409, 'd10_create_blocked', str(exc)) from exc
