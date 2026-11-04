"""B02: binding of the exact RADAR team policy v1.0 and effective complaint window.
No policy approval, no DB write, no human-review inference.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path

POLICY_ID=1
POLICY_LABEL='RADAR_TEAM_BASELINE_V1_20261026'
POLICY_SHA256='864491747d51703cdd01c588efb50372a512956f30497a4e2f53a80da6a0a45a'
POLICY_AUTHORITY='RADAR_TEAM_INTERNAL_ONLY_NOT_SEONGNAM_CITY'
SIMULATED_MARK='RADAR_TEAM_INTERNAL_DEMO_SIMULATED_APPROVAL'
EXPECTED_START=date(2021,1,1)
EXPECTED_END=date(2026,9,30)
DOMAINS={'accident':Decimal('0.30'),'hazard':Decimal('0.35'),'exposure':Decimal('0.20'),'vulnerability':Decimal('0.15')}

class B02ContractError(ValueError):pass

def _dec(value):
    if isinstance(value,bool):raise B02ContractError('BOOLEAN_NUMERIC_POLICY')
    try:x=Decimal(str(value))
    except (ValueError,InvalidOperation,TypeError) as e:raise B02ContractError('INVALID_NUMERIC_POLICY') from e
    if not x.is_finite():raise B02ContractError('NONFINITE_POLICY')
    return x

def validate_policy_document(document,*, start=None,end=None,setting=None, require_simulated_origin=False):
    if not isinstance(document,dict) or not isinstance(document.get('policy'),dict):
        raise B02ContractError('POLICY_DOCUMENT_REQUIRED')
    p=document['policy']
    if p.get('label')!=POLICY_LABEL:raise B02ContractError('POLICY_LABEL_MISMATCH')
    if document.get('policy_authority')!=POLICY_AUTHORITY:raise B02ContractError('POLICY_AUTHORITY_MISMATCH')
    if (p.get('normalization'),p.get('observation'),p.get('missing'),p.get('accident_reduce'))!=('positive_mid','scope_aware','renormalize','mean'):
        raise B02ContractError('POLICY_METHOD_MISMATCH')
    weights=p.get('domain_weights')
    if not isinstance(weights,dict) or set(weights)!=set(DOMAINS) or any(_dec(weights[k])!=v for k,v in DOMAINS.items()):
        raise B02ContractError('POLICY_WEIGHTS_MISMATCH')
    if document.get('complaint_mode')!='inside_hazard' or _dec(document.get('complaint_strength'))!=Decimal('0.15'):
        raise B02ContractError('COMPLAINT_COEFFICIENT_MISMATCH')
    if document.get('accident_exclusion')!='reweight_observed_nonaccident':
        raise B02ContractError('ACCIDENT_EXCLUSION_MISMATCH')
    if _dec(document.get('selection_min_score'))!=Decimal('70'):
        raise B02ContractError('SELECTION_THRESHOLD_MISMATCH')
    bounds=document.get('confidence_thresholds')
    if not isinstance(bounds,dict) or set(bounds)!={'medium','high'} or _dec(bounds['medium'])!=Decimal(6)/Decimal(9) and abs(_dec(bounds['medium'])-Decimal(6)/Decimal(9))>Decimal('0.000000000001'):
        raise B02ContractError('CONFIDENCE_MEDIUM_MISMATCH')
    if abs(_dec(bounds['high'])-Decimal(8)/Decimal(9))>Decimal('0.000000000001'):
        raise B02ContractError('CONFIDENCE_HIGH_MISMATCH')
    try: pstart=date.fromisoformat(document['input_period_start']);pend=date.fromisoformat(document['input_period_end'])
    except (ValueError,KeyError,TypeError) as e:raise B02ContractError('POLICY_PERIOD_INVALID') from e
    if (pstart,pend)!=(EXPECTED_START,EXPECTED_END):raise B02ContractError('POLICY_PERIOD_MISMATCH')
    if start is not None or end is not None:
        if start!=EXPECTED_START or end!=EXPECTED_END:raise B02ContractError('RUN_PERIOD_MISMATCH')
    if setting is not None:
        if int(setting.get('setting_version_id',-1))!=POLICY_ID:raise B02ContractError('SETTING_ID_MISMATCH')
        if setting.get('version_label')!=POLICY_LABEL:raise B02ContractError('SETTING_LABEL_MISMATCH')
        if setting.get('content_ref')!='sha256:'+POLICY_SHA256:raise B02ContractError('SETTING_REFERENCE_MISMATCH')
        if setting.get('approval_status') not in ('승인','APPROVED') or not setting.get('approved_at'):
            raise B02ContractError('SETTING_STATUS_MISMATCH')
        if require_simulated_origin and SIMULATED_MARK not in (setting.get('review_comment') or ''):
            raise B02ContractError('SIMULATED_APPROVAL_MARKER_MISSING')
    return {'setting_version_id':POLICY_ID,'policy_sha256':POLICY_SHA256,
            'authority':POLICY_AUTHORITY,'approval_scope':'INTERNAL_DEMO_SIMULATED_ONLY',
            'weights':{k:float(v) for k,v in DOMAINS.items()},
            'normalization':'positive_mid','observation':'scope_aware','missing':'renormalize',
            'accident_reduce':'mean','complaint_mode':'inside_hazard','complaint_strength':0.15,
            'confidence_medium':'6/9','confidence_high':'8/9','selection_min_score':70,
            'complaint_period_start':pstart.isoformat(),'complaint_period_end':pend.isoformat(),
            'score_formula':'base=100*sum(weight(domain)*normalized_domain)/sum(weight(observed_domains)); final=base + 100*effective_hazard_weight*0.15*(normalized_complaint_signal-normalized_hazard)',
            'official_city_approval':False}

def read_immutable_document(evidence_dir,setting):
    path=Path(evidence_dir).resolve()/'policies'/(POLICY_SHA256+'.json')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=POLICY_SHA256:raise B02ContractError('POLICY_BYTES_SHA256_MISMATCH')
    try:doc=json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError,ValueError) as e:raise B02ContractError('POLICY_JSON_INVALID') from e
    return doc,validate_policy_document(doc,setting=setting,require_simulated_origin=True)
