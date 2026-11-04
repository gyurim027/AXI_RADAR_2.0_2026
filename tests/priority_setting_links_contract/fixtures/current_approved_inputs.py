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


def classification_decision(row: dict) -> str | None:
    """Return Y/N for accepted classified inputs; None for excluded/unresolved.

    Human CONFIRMED overrides the accepted AI/rule classification only when its
    relevance is explicit. Unknowns are not inferred into negative cases.
    """
    relevance = row.get('relevance')
    status = str(row.get('review_status') or '').strip().upper()
    method = row.get('class_method')
    if relevance in ('Y', '보행안전 관련'):
        value = 'Y'
    elif relevance in ('N', '비관련'):
        value = 'N'
    else:
        return None
    if status == 'CONFIRMED' or method in ('AI', '규칙'):
        return value
    return None


def aggregate_reviewed_complaints(rows: list[dict], *, start: date, end: date,
                                  gids: set[str], confirmed_status='CONFIRMED') -> list[dict]:
    """Aggregate eligible classification; record unresolved rows without inventing values.

    This is a pure pre-score input calculation, not approval for a DB77/78 write.
    """
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise InputBlocked('INVALID_PERIOD')
    gids = {str(g) for g in gids}
    state = {gid: {'gid': gid, 'relevant_count': 0, 'repeat_count': 0,
                   'count_excl_low': 0, 'classification_status': 'COMPLETE',
                   'unresolved_count': 0, 'irrelevant_count': 0,
                   'low_excluded_count': 0} for gid in gids}
    seen_ids = set()
    seen_gid_type_dates = defaultdict(set)
    selected = []
    for row in rows:
        cid = row.get('complaint_id')
        if cid is None or not str(cid).strip() or str(cid) in seen_ids:
            raise InputBlocked('DUPLICATE_OR_EMPTY_COMPLAINT_ID')
        seen_ids.add(str(cid))
        dt = row.get('received_date')
        if isinstance(dt, str):
            try:
                dt = date.fromisoformat(dt[:10])
            except ValueError as exc:
                raise InputBlocked('INVALID_RECEIVED_DATE') from exc
        if not isinstance(dt, date):
            raise InputBlocked('INVALID_RECEIVED_DATE')
        if not start <= dt <= end:
            continue
        gid = str(row.get('gid'))
        if gid not in gids:
            raise InputBlocked('UNMAPPED_COMPLAINT_GID')
        target = state[gid]
        relevant = classification_decision(row)
        if relevant is None:
            target['unresolved_count'] += 1
            target['classification_status'] = 'INCOMPLETE'
            continue
        if relevant == 'N':
            target['irrelevant_count'] += 1
            continue
        typ = row.get('ped_type')
        if not isinstance(typ, str) or not typ.strip():
            target['unresolved_count'] += 1
            target['classification_status'] = 'INCOMPLETE'
            continue
        target['relevant_count'] += 1
        # Missing confidence/coordinate quality is not evidence of high quality.
        low = row.get('low_confidence')
        if low is None:
            low = str(row.get('coord_accuracy') or '').strip() == '낮음'
        if low is True:
            target['low_excluded_count'] += 1
        else:
            target['count_excl_low'] += 1
        selected.append((gid, typ, dt, str(cid)))
    for gid, typ, dt, cid in sorted(selected):
        dates = seen_gid_type_dates[(gid, typ)]
        if dates and dt not in dates:
            state[gid]['repeat_count'] += 1
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
