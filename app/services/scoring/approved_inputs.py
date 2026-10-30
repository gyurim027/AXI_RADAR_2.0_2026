"""Production input contract: only approved 62 policies and fully reviewed C-08 rows.

Pure reusable functions; database adapter stays in current RADAR code.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

class InputBlocked(ValueError):
    pass

REQUIRED_POLICY = {'label','normalization','observation','domain_weights','accident_reduce','missing'}
REQUIRED_DOMAINS = {'accident','hazard','exposure','vulnerability'}

def load_approved_policy(setting: dict, evidence_dir: str) -> dict:
    """Resolve 62.content_ref to an immutable file and ensure the policy is usable.
    This does not approve an unapproved row or select a policy on behalf of humans.
    """
    if setting.get('approval_status') not in ('승인','APPROVED') or not setting.get('approved_at'):
        raise InputBlocked('SETTING_NOT_APPROVED')
    ref = setting.get('content_ref')
    if not isinstance(ref,str) or not ref.startswith('sha256:') or len(ref)!=71:
        raise InputBlocked('SETTING_REFERENCE_INVALID')
    digest = ref[7:]
    if any(c not in '0123456789abcdef' for c in digest):
        raise InputBlocked('SETTING_DIGEST_INVALID')
    path=Path(evidence_dir).resolve()/'policies'/(digest+'.json')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=digest:
        raise InputBlocked('SETTING_CONTENT_MISMATCH')
    data=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data,dict):
        raise InputBlocked('SETTING_DOCUMENT_INVALID')
    policy=data.get('policy',data)
    if not isinstance(policy,dict) or not REQUIRED_POLICY <= set(policy):
        raise InputBlocked('INCOMPLETE_POLICY')
    if policy['label']!=setting.get('version_label'):
        raise InputBlocked('SETTING_VERSION_MISMATCH')
    if str(policy['label']).startswith('EXP_') or data.get('input_status')=='EXPLORATORY_PROXY':
        raise InputBlocked('EXPLORATORY_POLICY_NOT_ALLOWED')
    weights=policy['domain_weights']
    if not isinstance(weights,dict) or set(weights)!=REQUIRED_DOMAINS:
        raise InputBlocked('INVALID_DOMAIN_WEIGHTS')
    try:
        ws=[Decimal(str(x)) for x in weights.values()]
    except Exception as exc:
        raise InputBlocked('INVALID_DOMAIN_WEIGHTS') from exc
    if not all(x.is_finite() and x>0 for x in ws) or abs(sum(ws)-Decimal(1))>Decimal('0.000001'):
        raise InputBlocked('INVALID_DOMAIN_WEIGHTS')
    return policy


def aggregate_reviewed_complaints(rows: list[dict], *, start: date, end: date,
                                  gids: set[str], confirmed_status='CONFIRMED') -> list[dict]:
    """Aggregate reviewed complaint records by grid, preserving zero-complaint grids.

    Input rows are joined upstream to original complaint_id and C-08 reviewer decision.
    Each row requires independent human confirmation; rules alone never authorize inclusion.
    repeat_count counts a later distinct received date for an already seen gid/type.
    """
    if not isinstance(start,date) or not isinstance(end,date) or start>end:
        raise InputBlocked('INVALID_PERIOD')
    state={gid:{'gid':gid,'relevant_count':0,'repeat_count':0,'count_excl_low':0,
                'classification_status':'COMPLETE'} for gid in gids}
    seen_ids=set(); seen_gid_type_dates=defaultdict(set)
    selected=[]
    for row in rows:
        cid=row.get('complaint_id'); gid=row.get('gid')
        if not cid or cid in seen_ids:
            raise InputBlocked('DUPLICATE_OR_EMPTY_COMPLAINT_ID')
        seen_ids.add(cid)
        dt=row.get('received_date')
        if isinstance(dt,str):
            try: dt=date.fromisoformat(dt[:10])
            except ValueError as exc: raise InputBlocked('INVALID_RECEIVED_DATE') from exc
        if not isinstance(dt,date):
            raise InputBlocked('INVALID_RECEIVED_DATE')
        if not start<=dt<=end: continue
        if gid not in gids:
            raise InputBlocked('UNMAPPED_COMPLAINT_GID')
        if row.get('review_status')!=confirmed_status:
            raise InputBlocked('UNREVIEWED_COMPLAINT_IN_OFFICIAL_INPUT')
        relevant=row.get('relevance')
        if relevant not in ('Y','N'):
            raise InputBlocked('UNRESOLVED_RELEVANCE')
        if relevant=='N':continue
        typ=row.get('ped_type')
        if not isinstance(typ,str) or not typ:
            raise InputBlocked('MISSING_APPROVED_PED_TYPE')
        selected.append((gid,typ,dt,row))
        state[gid]['relevant_count']+=1
        if row.get('low_confidence') is not True:
            state[gid]['count_excl_low']+=1
    for gid,typ,dt,row in sorted(selected,key=lambda v:(v[0],v[1],v[2])):
        dates=seen_gid_type_dates[(gid,typ)]
        if dates and dt not in dates:
            state[gid]['repeat_count']+=1
        dates.add(dt)
    return [state[gid] for gid in sorted(state)]


def read_approved_policy_document(setting: dict, evidence_dir: str) -> dict:
    """Read an approved 62 policy by immutable digest; never infer approval."""
    load_approved_policy(setting,evidence_dir)  # approval, hash, weight checks
    ref=setting['content_ref']
    raw=(Path(evidence_dir).resolve()/'policies'/(ref[7:]+'.json')).read_bytes()
    data=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data,dict) or not isinstance(data.get('policy'),dict):
        raise InputBlocked('APPROVED_POLICY_DOCUMENT_INCOMPLETE')
    return data
