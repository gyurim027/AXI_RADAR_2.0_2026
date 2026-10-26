"""Authenticated C-08 type pre-review, sidecar only; no MySQL mutations or official approval.

The authenticated actor is derived from JWT AND current app_user row, never client input.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core import db
from app.core.auth import current_user, public_user, INACTIVE
from app.core.responses import ApiError
from app.services.c08.type_prereview import append_local_event, reconcile
from app.services.c08 import mysql_test_store

router = APIRouter(prefix='/api/c08/type-prereview', tags=['C08 유형 사전검수 (격리)'])

class TypeReviewRequest(BaseModel):
    complaint_id: str = Field(min_length=1, max_length=128)
    decision: str
    reason: str = Field(min_length=8, max_length=1000)

def _paths():
    root = Path(os.environ.get('RADAR_Q3_LOCAL_ROOT', 'out')).resolve()
    source = root / 'q3_rows_local.sqlite'
    ledger = root / 'q3_type_prereview_ledger.sqlite'
    if not source.is_file():
        raise ApiError(503, 'candidate_data_missing', '격리 후보 DB가 없습니다')
    if source == ledger: raise ApiError(503, 'path_collision', '저장소 경로 충돌')
    return source, ledger

def verified_operator(user: dict = Depends(current_user)) -> dict:
    """Fail closed on role change, deactivation and missing records."""
    try:
        rows = db.read_only('SELECT user_id, login_id, display_name, org_name, team_name, gu_name, role, is_active FROM app_user WHERE user_id=%s', (user['user_id'],))
    except Exception:
        raise ApiError(503, 'identity_source_unavailable', '현재 계정 검증 불가') from None
    if len(rows) != 1: raise ApiError(403, 'identity_not_found', '계정 확인 불가')
    row = rows[0]
    if str(row.get('is_active') or '').strip().lower() in INACTIVE or not str(row.get('is_active') or '').strip():
        raise ApiError(403, 'inactive_account', '비활성 계정')
    live = public_user(row)
    if (live['role'] != 'operator' or user.get('role') != 'operator' or
        str(live['user_id']) != str(user.get('user_id')) or
        live['login_id'] != user.get('login_id')):
        raise ApiError(403, 'operator_required', '운영자 권한 또는 토큰 정보 불일치')
    return live

@router.post('/reviews')
def create_type_review(body: TypeReviewRequest, actor: dict = Depends(verified_operator)):
    source, ledger = _paths()
    try:
        if os.environ.get("RADAR_Q3_STORE") == "mysql_test":
            result = mysql_test_store.append_review(source, body.complaint_id,
                body.decision, f"app_user:{actor['user_id']}", body.reason)
        else:
            result = append_local_event(source, ledger, body.complaint_id,
                body.decision, f"app_user:{actor['user_id']}", body.reason)
    except (ValueError, FileNotFoundError) as exc:
        raise ApiError(409, 'review_rejected', str(exc)) from None
    return {'ok': True, 'event_sha256': result['event_sha256'],
            'scope': 'TYPE_ONLY_LOCAL_UNAUTHENTICATED',
            'actor_user_id': actor['user_id'], 'official_approval': False,
            'c07_official_allowed': False}

@router.get('/status')
def type_review_status(start: str, end: str, actor: dict = Depends(verified_operator)):
    source, ledger = _paths()
    if len(start) != 10 or len(end) != 10 or start > end:
        raise ApiError(422, 'invalid_period', '기간을 확인하세요')
    try:
        if os.environ.get("RADAR_Q3_STORE") == "mysql_test":
            result = mysql_test_store.status(source, start, end)
        else:
            result = reconcile(source, ledger, start, end)
    except (ValueError, OSError) as exc:
        raise ApiError(409, 'ledger_invalid', str(exc)) from None
    result.pop('local_grid_summary', None)
    return result
