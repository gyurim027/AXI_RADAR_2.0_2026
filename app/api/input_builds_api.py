"""Authenticated DB59 input build registration and separate source-audit review.

Explicit calls save only DB59 and DB70; never create runs or start scoring.
"""
from datetime import date
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.scoring.input_builds import register_build, approve_build, read_build_status, BuildBlocked, BuildCommitUnconfirmed

router=APIRouter(prefix='/api/input-builds',tags=['산정 입력 판본·원천감사'])

class BuildBody(BaseModel):
    model_config=ConfigDict(populate_by_name=True,extra='forbid')
    period_start:date=Field(alias='periodStart')
    period_end:date=Field(alias='periodEnd')
    expected_audit_sha256:str=Field(alias='expectedAuditSha256',pattern=r'^[0-9a-f]{64}$')
    policy_sha256:str=Field(alias='policySha256',pattern=r'^[0-9a-f]{64}$')
    setting_ids:list[StrictInt]=Field(alias='settingIds',min_length=3,max_length=3)

class ReviewBody(BaseModel):
    model_config=ConfigDict(populate_by_name=True,extra='forbid')
    expected_manifest_sha256:str=Field(alias='expectedManifestSha256',pattern=r'^[0-9a-f]{64}$')

@router.post('')
def register(body:BuildBody,user:dict=Depends(require_roles('operator'))):
    data=body.model_dump()
    data['start']=data.pop('period_start');data['end']=data.pop('period_end')
    try:return register_build(user=user,**data,explicit_registration_approval=True)
    except BuildCommitUnconfirmed:raise ApiError(503,'input_build_commit_unconfirmed','입력 판본 저장 결과를 확인한 뒤 진행하세요. 자동 재시도하지 마세요.') from None
    except ValueError as exc:raise ApiError(409,'input_build_registration_blocked',str(exc)) from None

@router.post('/{row_id}/review')
def review(body:ReviewBody,row_id:int=Path(gt=0,le=9223372036854775807),user:dict=Depends(require_roles('city'))):
    try:return approve_build(row_id,user=user,**body.model_dump(),explicit_approval=True)
    except BuildCommitUnconfirmed:raise ApiError(503,'input_build_review_commit_unconfirmed','감사 승인 저장 결과를 확인한 뒤 진행하세요. 자동 재시도하지 마세요.') from None
    except ValueError as exc:raise ApiError(409,'input_build_review_blocked',str(exc)) from None

@router.get('/{row_id}')
def detail(row_id:int=Path(gt=0,le=9223372036854775807),user:dict=Depends(require_roles('operator','city'))):
    try:return read_build_status(row_id)
    except ValueError as exc:raise ApiError(409,'input_build_lookup_blocked',str(exc)) from None
