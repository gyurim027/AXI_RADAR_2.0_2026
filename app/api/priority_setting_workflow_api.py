"""I-02: versioned 62 scoring policy proposal/review. No new DB tables.

This API cannot invent a policy or an approval. It persists a user-supplied,
content-addressed JSON policy and records the authenticated actual actor.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict

from app.core import db
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.scoring.approved_inputs import REQUIRED_DOMAINS, REQUIRED_POLICY

router = APIRouter(prefix='/api/settings/versions', tags=['I-02 산정기준 제안·검토'])

class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = '가중치'
    label: str = Field(min_length=1,max_length=255)
    document: dict

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str
    reference: str = Field(min_length=1,max_length=255)


def _policy_validate(d: dict, label: str):
    p=d.get('policy',d)
    if not isinstance(p,dict) or not REQUIRED_POLICY.issubset(p):
        raise ApiError(422,'policy_incomplete','필수 평가기준 항목 누락')
    if p['label'] != label or label.startswith('EXP_') or d.get('input_status')=='EXPLORATORY_PROXY':
        raise ApiError(422,'policy_label','공식 판본명과 정책 문서가 일치하지 않습니다')
    w=p.get('domain_weights')
    if not isinstance(w,dict) or set(w)!=REQUIRED_DOMAINS:
        raise ApiError(422,'weights','평가분야 가중치 4종이 필요합니다')
    from decimal import Decimal, InvalidOperation
    try:
        weights=[Decimal(str(x)) for x in w.values()]
    except (InvalidOperation,ValueError):
        raise ApiError(422,'weights','가중치가 숫자가 아닙니다') from None
    if any(not x.is_finite() or x<=0 for x in weights) or abs(sum(weights)-Decimal(1))>Decimal('0.000001'):
        raise ApiError(422,'weights','가중치는 양수이고 합계가 1이어야 합니다')
    for name in ('complaint_mode','complaint_strength','confidence_thresholds','accident_exclusion','selection_min_score'):
        if name not in d:
            raise ApiError(422,'policy_incomplete',f'공식 실행계약 누락: {name}')
    if d['complaint_mode'] not in ('independent','inside_hazard','bonus'):
        raise ApiError(422,'mode','지원하지 않는 결합 방식')
    try:
        strength=Decimal(str(d['complaint_strength']))
        minimum=Decimal(str(d['selection_min_score']))
    except (InvalidOperation,ValueError):
        raise ApiError(422,'policy_range','산정 계수 형식 오류') from None
    if not strength.is_finite() or not 0<=strength<=1 or not minimum.is_finite() or not 0<=minimum<=100:
        raise ApiError(422,'policy_range','산정 계수 범위 오류')
    if d['accident_exclusion']!='reweight_observed_nonaccident':
        raise ApiError(422,'accident_exclusion','지원하지 않는 사고 제외 방식')
    thresholds=d['confidence_thresholds']
    if not isinstance(thresholds,dict) or set(thresholds)!={'high','medium'}:
        raise ApiError(422,'confidence','신뢰도 경계값 오류')
    try:
        lo=Decimal(str(thresholds['medium']));hi=Decimal(str(thresholds['high']))
    except (InvalidOperation,ValueError):
        raise ApiError(422,'confidence','신뢰도 경계값 형식 오류') from None
    if not lo.is_finite() or not hi.is_finite() or not 0<=lo<hi<=1:
        raise ApiError(422,'confidence','신뢰도 경계값 범위 오류')


def _policy_home()->Path:
    root=os.environ.get('RADAR_PRIORITY_EVIDENCE_DIR')
    if not root:
        raise ApiError(503,'evidence_storage_missing','RADAR_PRIORITY_EVIDENCE_DIR 영속 경로가 필요합니다')
    path=Path(root).expanduser().resolve()/'policies'
    path.mkdir(parents=True,exist_ok=True)
    return path


def _durable_document(doc: dict)->str:
    raw=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    digest=sha256(raw).hexdigest()
    target=_policy_home()/(digest+'.json')
    if target.exists():
        if target.read_bytes()!=raw:
            raise ApiError(409,'policy_digest_conflict','기존 정책 파일과 내용 충돌')
    else:
        fd,tmp=tempfile.mkstemp(dir=str(target.parent),prefix='.policy-')
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return 'sha256:'+digest


def _verify_pointer(ref:str)->None:
    if not isinstance(ref,str) or not ref.startswith('sha256:') or len(ref)!=71:
        raise ApiError(409,'invalid_pointer','62 원본 참조 형식 오류')
    p=_policy_home()/(ref[7:]+'.json')
    if not p.is_file() or sha256(p.read_bytes()).hexdigest()!=ref[7:]:
        raise ApiError(409,'policy_file_not_verified','승인 대상 정책 원본이 없거나 변조됐습니다')


@router.post('/proposals',status_code=201)
def propose(body:Proposal,user:dict=Depends(require_roles('operator'))):
    if body.kind not in ('가중치','기준값','우선 확인 조건'):
        raise ApiError(422,'kind','설정 종류 오류')
    _policy_validate(body.document,body.label)
    ref=_durable_document(body.document)
    with db.connect() as con:
        with con.cursor() as cur:
            # 62 bigint PK is not AUTO_INCREMENT in currently observed schema.
            # Serialize ID allocation with a named MySQL lock, not MAX(id) FOR UPDATE.
            cur.execute("SELECT GET_LOCK('radar_setting62_id',10) AS locked")
            if cur.fetchone()['locked']!=1:
                raise ApiError(503,'id_allocation_busy','설정판본 등록 동시성 잠금 실패')
            try:
                cur.execute('SELECT setting_version_id FROM setting_version WHERE content_ref=%s AND setting_kind=%s FOR UPDATE',(ref,body.kind))
                existed=cur.fetchone()
                if existed:
                    return {'status':'EXISTS','setting_version_id':existed['setting_version_id'],'content_ref':ref}
                cur.execute('SELECT COALESCE(MAX(setting_version_id),0)+1 AS nid FROM setting_version')
                new_id=int(cur.fetchone()['nid'])
                cur.execute('INSERT INTO setting_version(setting_version_id,setting_kind,version_label,content_ref,proposed_by,proposed_at,approval_status) VALUES (%s,%s,%s,%s,%s,NOW(),%s)',(new_id,body.kind,body.label,ref,int(user['user_id']),'제안'))
                con.commit()
            finally:
                cur.execute("SELECT RELEASE_LOCK('radar_setting62_id')")
    return {'status':'PROPOSED','setting_version_id':new_id,'content_ref':ref,'proposed_by':int(user['user_id'])}


@router.post('/{setting_id}/review')
def review(setting_id:int,body:Decision,user:dict=Depends(require_roles('city'))):
    if body.decision not in ('승인','돌려보냄'):
        raise ApiError(422,'decision','승인 또는 돌려보냄만 가능합니다')
    with db.connect() as con:
        with con.cursor() as cur:
            cur.execute('SELECT setting_version_id,proposed_by,approval_status,content_ref FROM setting_version WHERE setting_version_id=%s FOR UPDATE',(setting_id,))
            found=cur.fetchone()
            if not found:
                raise ApiError(404,'setting_not_found','설정판본 없음')
            if found['approval_status']!='제안':
                raise ApiError(409,'already_decided','제안 상태가 아닙니다')
            if int(found['proposed_by'])==int(user['user_id']):
                raise ApiError(403,'self_approval','제안자와 승인자는 달라야 합니다')
            if body.decision=='승인':
                _verify_pointer(found['content_ref'])
            cur.execute('UPDATE setting_version SET approval_status=%s,approved_by=%s,approved_at=CASE WHEN %s=%s THEN NOW() ELSE NULL END,review_comment=%s WHERE setting_version_id=%s AND approval_status=%s',(body.decision,int(user['user_id']),body.decision,'승인',body.reference,setting_id,'제안'))
            if cur.rowcount!=1:
                raise ApiError(409,'concurrent_review','동시에 변경된 제안')
        con.commit()
    return {'setting_version_id':setting_id,'status':body.decision,'reviewed_by':int(user['user_id']),'reference':body.reference}
