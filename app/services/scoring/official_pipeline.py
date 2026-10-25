"""RADAR official-run join: 62 policy -> reviewed C-08 -> C-07 counts -> 77/78.

Does not approve policy, invent human review, fabricate detail metrics, or modify schema.
The caller supplies the authoritative, reviewed dataset and full scored evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json

from app.services.scoring.approved_inputs import (
    InputBlocked, aggregate_reviewed_complaints, load_approved_policy,
)
from app.services.scoring.production_writer import OfficialBatch, ProductionBlocked
from app.services.scoring.mysql_writer import write_approved_batch


def _sha(obj):
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class OfficialInputs:
    setting_version_id: int
    policy_evidence_dir: str
    build_id: str
    start: date
    end: date
    gids: frozenset[str]
    reviewed_complaints: tuple[dict, ...]
    # The actual output of a configured scoring engine, including five evidence fields.
    scored_candidates: tuple[dict, ...]
    evidence_by_gid: dict
    authorized_by: str
    approval_reference: str


def run_official_pipeline(inputs: OfficialInputs, *, explicit_db_write_approval: bool,
                          read_only=None, connection_factory=None) -> dict:
    """Perform the existing full input join and invoke the existing 77/78 writer.

    This is intentionally *not* an independent alternative scoring engine.
    All official scores MUST originate upstream from the selected, approved engine.
    """
    if read_only is None:
        from app.core.db import read_only
    if not inputs.gids:
        raise InputBlocked('GRID_POPULATION_EMPTY')
    rows = read_only(
        'SELECT setting_version_id,setting_kind,version_label,content_ref,approval_status,approved_at '
        'FROM setting_version WHERE setting_version_id=%s', (inputs.setting_version_id,))
    if len(rows) != 1:
        raise InputBlocked('SETTING_NOT_FOUND')
    setting = rows[0]
    policy = load_approved_policy(setting, inputs.policy_evidence_dir)

    # C-07 output is generated only from explicitly human-confirmed input, not AI candidates.
    counts = aggregate_reviewed_complaints(list(inputs.reviewed_complaints),
                                            start=inputs.start, end=inputs.end,
                                            gids=set(inputs.gids))
    count_by_gid = {r['gid']: r for r in counts}
    scored_by_gid = {r['gid']: r for r in inputs.scored_candidates}
    if len(scored_by_gid) != len(inputs.scored_candidates) or set(scored_by_gid) != set(inputs.gids):
        raise InputBlocked('SCORE_GRID_POPULATION_MISMATCH')
    if set(inputs.evidence_by_gid) != set(inputs.gids):
        raise InputBlocked('EVIDENCE_GRID_POPULATION_MISMATCH')

    candidates = []
    for gid in sorted(inputs.gids):
        source = scored_by_gid[gid]
        counts_row = count_by_gid[gid]
        # Forbid subtly mismatched counts in the precomputed engine output.
        if (source.get('complaint_cnt') != counts_row['relevant_count'] or
                source.get('complaint_cnt_excl_low') != counts_row['count_excl_low']):
            raise InputBlocked('SCORING_COMPLAINT_INPUT_MISMATCH:' + gid)
        if source.get('calculation_status') != 'OFFICIAL' or source.get('input_status') != 'VERIFIED_CLASSIFIED':
            raise InputBlocked('NON_OFFICIAL_CALCULATION:' + gid)
        if source.get('classification_status') != 'COMPLETE':
            raise InputBlocked('INCOMPLETE_CLASSIFICATION:' + gid)
        candidates.append(dict(source))

    reviewed_manifest = [
        {'complaint_id': r['complaint_id'], 'gid': r['gid'], 'relevance': r['relevance'],
         'ped_type': r.get('ped_type'), 'received_date': str(r.get('received_date')),
         'review_status': r.get('review_status')}
        for r in inputs.reviewed_complaints
    ]
    contract = {'start': str(inputs.start), 'end': str(inputs.end),
                'reviewed_manifest_sha256': _sha(reviewed_manifest),
                'grid_count': len(inputs.gids), 'repeat_rule': 'distinct_received_dates_per_gid_type'}
    batch = OfficialBatch(
        build_id=inputs.build_id,
        rule_version=policy['label'],
        setting_version_id=inputs.setting_version_id,
        setting_content_ref=setting['content_ref'],
        input_digest=_sha({'build_id': inputs.build_id, 'gids': sorted(inputs.gids),
                           'scores': [(r['gid'], str(r['official_score'])) for r in candidates]}),
        policy_digest=setting['content_ref'].removeprefix('sha256:'),
        complaint_contract_digest=_sha(contract),
        candidates=tuple(candidates),
        authorized_by=inputs.authorized_by,
        approval_reference=inputs.approval_reference,
    )
    written = write_approved_batch(batch,
        explicit_db_write_approval=explicit_db_write_approval,
        evidence_by_gid=inputs.evidence_by_gid,
        connection_factory=connection_factory)
    return {**written, 'setting_version_id': inputs.setting_version_id,
            'reviewed_complaint_count': len(reviewed_manifest),
            'complaint_count_in_period': sum(x['relevant_count'] for x in counts),
            'source_contract_sha256': _sha(contract)}
