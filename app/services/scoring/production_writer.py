"""Fail-closed, opt-in MySQL 77/78 writer.

Never derives official scores from exploratory proxy runs. 82 is a human-action
record, not a row that the scorer may invent. No schema mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


class ProductionBlocked(ValueError):
    pass


@dataclass(frozen=True)
class OfficialBatch:
    build_id: str
    rule_version: str
    setting_version_id: int
    setting_content_ref: str
    input_digest: str
    policy_digest: str
    complaint_contract_digest: str
    candidates: tuple[dict, ...]
    # Human-approved attestation is evidence *provided externally*, never inferred.
    authorized_by: str
    approval_reference: str


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ProductionBlocked('MISSING_' + name)
    return value


def validate_batch(batch: OfficialBatch):
    for field in ('build_id', 'rule_version', 'setting_content_ref', 'input_digest',
                  'policy_digest', 'complaint_contract_digest', 'authorized_by', 'approval_reference'):
        _nonempty(getattr(batch, field), field.upper())
    for field in ('input_digest', 'policy_digest', 'complaint_contract_digest'):
        val = getattr(batch, field)
        if len(val) != 64 or any(c not in '0123456789abcdef' for c in val):
            raise ProductionBlocked('INVALID_DIGEST_' + field)
    if type(batch.setting_version_id) is not int or batch.setting_version_id <= 0:
        raise ProductionBlocked('INVALID_SETTING_ID')
    if not batch.candidates:
        raise ProductionBlocked('EMPTY_RESULTS')
    seen = set()
    for row in batch.candidates:
        if row.get('calculation_status') != 'OFFICIAL' or row.get('official_score') is None:
            raise ProductionBlocked('NON_OFFICIAL_OR_MISSING_SCORE')
        if row.get('input_status') != 'VERIFIED_CLASSIFIED' or row.get('classification_status') != 'COMPLETE':
            raise ProductionBlocked('UNVERIFIED_COMPLAINT_INPUT')
        if row.get('source_kind') in ('EXPLORATORY_PROXY', 'STUB', 'ILLUSTRATIVE'):
            raise ProductionBlocked('PROXY_INPUT')
        gid = _nonempty(row.get('gid'), 'GID')
        if gid in seen:
            raise ProductionBlocked('DUPLICATE_GID')
        seen.add(gid)
        try:
            value = Decimal(str(row['official_score']))
        except (InvalidOperation, ValueError):
            raise ProductionBlocked('INVALID_SCORE') from None
        if not value.is_finite() or not 0 <= value <= 100:
            raise ProductionBlocked('INVALID_SCORE')
        rank = row.get('rank_no')
        if type(rank) is not int or rank <= 0:
            raise ProductionBlocked('INVALID_RANK')
        for col in ('complaint_cnt', 'complaint_cnt_excl_low'):
            if type(row.get(col)) is not int or row[col] < 0:
                raise ProductionBlocked('INVALID_COUNT')
        if row['complaint_cnt_excl_low'] > row['complaint_cnt']:
            raise ProductionBlocked('INVALID_COUNT_SUBSET')
        if row.get('selected_yn') not in (None, 'Y', 'N'):
            raise ProductionBlocked('INVALID_SELECTION')
    # Scorer contract: competition ranking after 4-decimal DB precision.
    # Ranking must be over exactly the candidate population being persisted.
    ordered = sorted(
        ((Decimal(str(row['official_score'])).quantize(Decimal('0.0001')), row['rank_no'])
         for row in batch.candidates),
        key=lambda pair: pair[0], reverse=True,
    )
    first_rank_by_score = {}
    for position, (score, actual_rank) in enumerate(ordered, start=1):
        expected_rank = first_rank_by_score.setdefault(score, position)
        if actual_rank != expected_rank:
            raise ProductionBlocked('RANK_SCORE_MISMATCH')
    return True


def plan(batch: OfficialBatch):
    """Pure planning: no DB access; useful before approved MySQL integration."""
    validate_batch(batch)
    identity = {'build_id':batch.build_id, 'rule_version':batch.rule_version,
                'setting_version_id':batch.setting_version_id,
                'input_digest':batch.input_digest, 'policy_digest':batch.policy_digest,
                'complaint_contract_digest':batch.complaint_contract_digest,
                'candidates':sorted(batch.candidates, key=lambda c:c['gid'])}
    fingerprint=sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False,default=str).encode()).hexdigest()
    return {'fingerprint':fingerprint,'candidate_count':len(batch.candidates),
            'authorized_reference':batch.approval_reference,
            'status':'VALIDATED_NOT_WRITTEN'}


def inspect_dependencies(read_only, batch: OfficialBatch):
    """Query only authoritative rows; reject absent/mismatched setting or build.

    `read_only` is app.core.db.read_only or a test double.
    """
    info = plan(batch)
    rows = read_only('SELECT setting_version_id, version_label, content_ref, approval_status, approved_at FROM setting_version WHERE setting_version_id=%s', (batch.setting_version_id,))
    if len(rows) != 1:
        raise ProductionBlocked('SETTING_NOT_FOUND')
    setting = rows[0]
    if setting['content_ref'] != batch.setting_content_ref:
        raise ProductionBlocked('SETTING_CONTENT_MISMATCH')
    if setting.get('approval_status') not in ('승인', 'APPROVED') or setting.get('approved_at') is None:
        raise ProductionBlocked('SETTING_NOT_APPROVED')
    if setting['version_label'] != batch.rule_version:
        raise ProductionBlocked('RULE_VERSION_MISMATCH')
    # NOTE: 77.build_id is not a verified 05 build registry. Don't assert a guessed build.
    matched = read_only('SELECT COUNT(*) AS n FROM grid_feature WHERE ID_gid IS NOT NULL', ())
    if not matched or int(matched[0]['n']) < len(batch.candidates):
        raise ProductionBlocked('GRID_POPULATION_MISMATCH')
    # Require every input grid to exist; no silent drop.
    for row in batch.candidates:
        present=read_only('SELECT ID_gid FROM grid_feature WHERE ID_gid=%s',(row['gid'],))
        if len(present)!=1:
            raise ProductionBlocked('GRID_ID_MISSING')
    return {**info,'status':'DEPENDENCIES_CHECKED_NOT_WRITTEN'}
