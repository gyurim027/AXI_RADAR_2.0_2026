"""Read-only calculation preparation; no policy approval or shared DB writes.

Reuses the team's calculator. All output is experimental until the outstanding
input, policy, round and storage contracts have independently been satisfied.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .calculation import (Policy, FEATURES, DOMAINS, calculate, normalize,
                          rank_scores, validate_complaint_input)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def number(value):
    return None if pd.isna(value) else float(value)


def resolve_setting(content, row):
    """Explicit, proposed content-addressed contract; never interpret arbitrary content_ref.

    The caller supplies exact file bytes and a selected 62 row. Existing opaque
    references need a team-approved adapter instead of heuristic decoding.
    """
    digest = sha256(content).hexdigest()
    if type(row.get('setting_version_id')) is not int or row['setting_version_id'] <= 0:
        raise ValueError('SETTING_ID_REQUIRED')
    if row.get('content_ref') != 'sha256:' + digest:
        raise ValueError('SETTING_CONTENT_HASH_MISMATCH_OR_UNSUPPORTED_REFERENCE')
    config = json.loads(content)
    policy = Policy(**config['policy'])
    policy.validate()
    if row.get('version_label') != policy.label:
        raise ValueError('SETTING_VERSION_MISMATCH')
    return config, {'setting_version_id': row['setting_version_id'],
                    'content_ref': row['content_ref'], 'policy_sha256': digest,
                    'approval_status': row.get('approval_status'),
                    'approved_by': row.get('approved_by'), 'approved_at': row.get('approved_at'),
                    'official_policy_verified': False}


def audit_source(rows):
    """Inventory only. NULL classification is pending, never a zero complaint count."""
    required = {'complaint_id', 'gid', 'relevance', 'class_confidence'}
    if not required <= set(rows):
        raise ValueError('SOURCE_COLUMNS_MISSING:' + ','.join(sorted(required - set(rows))))
    if rows.complaint_id.isna().any() or rows.complaint_id.duplicated().any():
        raise ValueError('SOURCE_ID_INVALID')
    pending = rows.relevance.isna() | rows.class_confidence.isna() | ~rows.relevance.isin(['보행안전 관련', '비관련', '불명'])
    pending |= rows.relevance.eq('불명')
    confidence = pd.to_numeric(rows.class_confidence, errors='coerce')
    pending |= ~confidence.between(0, 1)
    # These states overlap location counts; do not sum them as a partition.
    return {'source_rows': len(rows), 'pending_classification': int(pending.sum()),
            'grid_unassigned': int(rows.gid.isna().sum()),
            'related_labeled': int((~pending & rows.relevance.eq('보행안전 관련')).sum()),
            'not_related_labeled': int((~pending & rows.relevance.eq('비관련')).sum()),
            'classification_quality_verified': False,
            'partition': 'pending + related_labeled + not_related_labeled = source_rows; grid_unassigned overlaps',
            'official_eligible': False}


def prepare(grid, config, *, complaints=None, complaint_meta=None, source=None, setting=None):
    """Calculate available evidence and expose exact blocked stages without DB access.

    Five-detail fields have a stable shape. Confidence stays null until its
    independent policy is approved; a coverage fraction is not a confidence grade.
    Accident exclusion alternatives are explicitly base-stage diagnostics.
    """
    policy = Policy(**config['policy'])
    policy.validate()
    if config.get('comparison_population') != 'hazard_observed' or config.get('fit_population') != 'all_input_positive_counts':
        raise ValueError('UNSUPPORTED_POPULATION')
    mode = config['complaint_mode']
    q = config['coefficient_points']
    if mode not in ('bonus', 'independent', 'inside_hazard') or type(q) not in (int, float) or not np.isfinite(q) or not 0 <= q <= 100:
        raise ValueError('INVALID_COMPLAINT_POLICY')
    base, domains, contributions, states = calculate(grid, policy)
    complaint_errors = ['CLASSIFIED_AGGREGATE_NOT_SUPPLIED'] if complaints is None else validate_complaint_input(complaints, complaint_meta or {}, grid.ID_gid)
    audit = audit_source(source) if source is not None else None
    if source is None:
        complaint_errors.append('SOURCE_NOT_SUPPLIED')
    elif audit['pending_classification']:
        complaint_errors.append('SOURCE_CLASSIFICATION_PENDING')
    if complaints is not None:
        expected = (complaint_meta or {}).get('source_sha256')
        if not expected or expected != config.get('source_sha256'):
            complaint_errors.append('SOURCE_AGGREGATE_HASH_UNBOUND')
    signal = pd.Series(np.nan, index=base.index)
    counts = None
    if not complaint_errors:
        counts = complaints.set_index('gid').loc[grid.ID_gid].reset_index()
        signal = normalize(counts.relevant_count, policy.normalization)
    b = base.score
    term = q * signal
    adjustment = -q / 100 * b if mode == 'independent' else -q * domains.hazard if mode == 'inside_hazard' else pd.Series(0., index=b.index)
    pre = (1-q/100)*b+term if mode == 'independent' else b+q*(signal-domains.hazard) if mode == 'inside_hazard' else b+term
    total = (pre.clip(upper=100) if mode == 'bonus' else pre).where(domains.hazard.notna())
    ranked = rank_scores(total, grid.ID_gid)
    weights = pd.Series(policy.domain_weights)
    denominator = domains.notna().mul(weights).sum(axis=1)
    without = contributions.drop(columns=DOMAINS['accident']).sum(axis=1, min_count=1)
    without_denominator = denominator - domains.accident.notna() * weights['accident']
    renormalized = without * denominator / without_denominator.where(without_denominator.gt(0))
    rows = []
    for i, gid in enumerate(grid.ID_gid):
        reasons = {c: str(states.iloc[i][c]) for c in FEATURES if states.iloc[i][c] != 'RECORD_VALUE'}
        final = number(ranked.score.iloc[i])
        rows.append({'gid': gid, 'base_score': number(b.iloc[i]),
            'base_score_role': 'PRE_COMPLAINT_REFERENCE',
            'score': final, 'rank_no': None if pd.isna(ranked.rank_no.iloc[i]) else int(ranked.rank_no.iloc[i]),
            'calculation_status': 'UNSCORED' if final is None else 'EXPERIMENTAL',
            'complaint_cnt': None if counts is None else int(counts.relevant_count.iloc[i]),
            'complaint_signal_points': number(term.iloc[i]) if final is not None else None,
            'base_adjustment': number(adjustment.iloc[i]) if final is not None else None,
            'net_change': final-float(b.iloc[i]) if final is not None else None,
            'rounding_adjustment': final-float(total.iloc[i]) if final is not None else None,
            'details': {'domain_scores': {k: number(v*100) for k,v in domains.iloc[i].items()},
                'indicator_contributions': {k:number(v) for k,v in contributions.iloc[i].items()},
                'unevaluated_reasons': {'indicators':reasons, 'complaint':complaint_errors,
                    'confidence':['CONFIDENCE_POLICY_PENDING'], 'accident_exclusion':['POLICY_PENDING']},
                'confidence_grade': None, 'score_excluding_accidents': None},
            'detail_stage': 'BASE_BEFORE_COMPLAINT',
            'accident_exclusion_comparison': {'fixed_denominator':number(without.iloc[i]),
                'redistributed_denominator':number(renormalized.iloc[i]), 'stage':'BASE_BEFORE_COMPLAINT'},
            'observed_indicator_count':int(base.observed_indicator_count.iloc[i]),
            'effective_denominator':number(denominator.iloc[i])})
    return {'status':'PREPARED_NOT_OFFICIAL_NOT_WRITTEN', 'setting':setting,
        'policy':asdict(policy), 'complaint_audit':audit, 'rows':rows,
        'official_blockers':sorted(set(complaint_errors + ['POLICY_ADOPTION_PENDING',
            'CONFIDENCE_POLICY_PENDING','ACCIDENT_EXCLUSION_POLICY_PENDING',
            'D10_RUN_CONTRACT_PENDING','SHARED_DB_WRITE_NOT_AUTHORIZED'])),
        'source_kind':'ACTUAL_INPUT_EXPERIMENT', 'official_score_generated':False}


def execute_files(grid_path, source_path, config_path, *, aggregate_path=None,
                  metadata_path=None, setting_path=None):
    config_bytes = Path(config_path).read_bytes()
    setting = None
    if setting_path:
        config, setting = resolve_setting(config_bytes, json.loads(Path(setting_path).read_text(encoding='utf-8')))
    else:
        config = json.loads(config_bytes)
    inputs = {name:Path(path).read_bytes() for name,path in [('grid',grid_path),('source',source_path)]}
    config = {**config, 'source_sha256':sha256(inputs['source']).hexdigest()}
    out = prepare(pd.read_csv(grid_path), config, source=pd.read_csv(source_path, low_memory=False),
        complaints=pd.read_csv(aggregate_path) if aggregate_path else None,
        complaint_meta=json.loads(Path(metadata_path).read_text(encoding='utf-8')) if metadata_path else None,
        setting=setting)
    out['input_sha256']={k:sha256(v).hexdigest() for k,v in inputs.items()}
    out['config_sha256']=sha256(config_bytes).hexdigest()
    out['code_sha256']={n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('execution.py','calculation.py')}
    for name,path in [('aggregate',aggregate_path),('metadata',metadata_path),('setting',setting_path)]:
        if path: out['input_sha256'][name]=sha256(Path(path).read_bytes()).hexdigest()
    return out
