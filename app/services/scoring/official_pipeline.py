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
from app.services.scoring.setting_links import prepare_references
from app.services.scoring.approved_inputs import read_approved_policy_document


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
    setting_references: tuple = ()
    existing_run_id: int | None = None


def run_official_pipeline(inputs: OfficialInputs, *, explicit_db_write_approval: bool,
                          read_only=None, connection_factory=None, r02_prepared_input=None, r02_full_source_input=None,
                          preview_only: bool = False) -> dict:
    """Perform the existing full input join and invoke the existing 77/78 writer.

    This is intentionally *not* an independent alternative scoring engine.
    All official scores MUST originate upstream from the selected, approved engine.
    """
    if preview_only and explicit_db_write_approval:
        raise InputBlocked('PREVIEW_CANNOT_AUTHORIZE_DB_WRITE')
    if type(inputs.existing_run_id) is not int or inputs.existing_run_id <= 0:
        raise InputBlocked('D10_EXISTING_RUN_ID_REQUIRED')
    if inputs.existing_run_id == 1:
        raise InputBlocked('LEGACY_RUN1_OFFICIAL_ACCESS_BLOCKED')
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
    # Simulated 62 approval cannot authorize a real official 77/78 run.
    if inputs.setting_version_id == 1:
        from app.services.scoring.b02_policy_contract import validate_policy_document, read_immutable_document
        scoped = read_only('SELECT review_comment FROM setting_version WHERE setting_version_id=%s',(inputs.setting_version_id,))
        if not scoped: raise InputBlocked('SETTING_REVIEW_SCOPE_MISSING')
        scoped_setting={**setting, **scoped[0]}
        document, _ = read_immutable_document(inputs.policy_evidence_dir,scoped_setting)
        validate_policy_document(document,start=inputs.start,end=inputs.end,setting=scoped_setting,require_simulated_origin=True)
        if explicit_db_write_approval: raise InputBlocked('INTERNAL_DEMO_SIMULATION_CANNOT_WRITE_OFFICIAL_77_78')

    # 세 FK는 실제 계산 문서와 대조한 참조만 허용한다.
    document = read_approved_policy_document(setting, inputs.policy_evidence_dir)
    ids = tuple(r.setting_version_id for r in inputs.setting_references)
    verified = prepare_references(read_only, ids, inputs.policy_evidence_dir, document)
    if verified != inputs.setting_references:
        raise InputBlocked('SETTING_REFERENCES_CHANGED_DURING_CALCULATION')

    # Eligible AI/rule classifications may be counted; unresolved classifications remain blocked for official writes.
    # R02 two-policy full-source gateway: audit is required, no DB writes permitted.
    if r02_full_source_input is not None:
        from app.services.scoring.r02_full_source_quarantine import FullSourceR02, UNMAPPED_POLICY_ID
        from app.services.scoring.r02_explicit_exclusion import POLICY_ID as R02_MAPPED_POLICY_ID
        if explicit_db_write_approval and not inputs.build_id.startswith('db59:'):
            raise InputBlocked('R02_FULL_SOURCE_OFFICIAL_WRITES_BLOCKED')
        if r02_prepared_input is not None:
            raise InputBlocked('R02_AMBIGUOUS_INPUT_PATH')
        if not isinstance(r02_full_source_input, FullSourceR02):
            raise InputBlocked('R02_FULL_SOURCE_OBJECT_INVALID')
        full_audit = r02_full_source_input.audit
        prepared = r02_full_source_input.prepared
        import hashlib
        audit_payload = {k: v for k, v in full_audit.items() if k != 'audit_sha256'}
        computed_audit_sha = hashlib.sha256(json.dumps(audit_payload, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        if (full_audit.get('audit_sha256') != computed_audit_sha
                or full_audit.get('policy_mapped') != R02_MAPPED_POLICY_ID
                or full_audit.get('policy_unmapped') != UNMAPPED_POLICY_ID
                or full_audit.get('approved_for_official_write') is not False
                or full_audit.get('period_start') != inputs.start.isoformat()
                or full_audit.get('period_end') != inputs.end.isoformat()
                or full_audit.get('grid_count') != len(inputs.gids)
                or full_audit.get('prepared_grid_count') != len(inputs.gids)
                or full_audit.get('mapped_eligible_rows', -1) + full_audit.get('mapped_excluded_rows', -1) + full_audit.get('unmapped_quarantined_rows', -1) != full_audit.get('source_rows')
                or full_audit.get('mapped_rows', -1) != full_audit.get('mapped_eligible_rows', -1) + full_audit.get('mapped_excluded_rows', -1)
                or full_audit.get('mapped_excluded_sha256') != prepared.audit.get('excluded_manifest_sha256')
                or not full_audit.get('unmapped_quarantined_sha256')
                or not full_audit.get('audit_sha256')):
            raise InputBlocked('R02_FULL_SOURCE_AUDIT_MISMATCH')
        # Make the existing prepared-input validation apply as well.
        r02_prepared_input = prepared
    if r02_prepared_input is None:
        counts = aggregate_reviewed_complaints(list(inputs.reviewed_complaints),
                                                    start=inputs.start, end=inputs.end,
                                                    gids=set(inputs.gids))
    else:
        if explicit_db_write_approval and (r02_full_source_input is None or not inputs.build_id.startswith('db59:')):
            raise InputBlocked('R02_AUDIT_PERSISTENCE_AND_APPROVAL_NOT_VERIFIED')
        from app.services.scoring.r02_official_input_bridge import PreparedR02
        if not isinstance(r02_prepared_input, PreparedR02):
            raise InputBlocked('R02_PREPARED_INPUT_INVALID')
        audit = r02_prepared_input.audit
        if (audit.get('policy_id') != 'R02_UNRESOLVED_EXCLUSION_TEAM_SELECTED_20261101_V1'
                or audit.get('approved_for_official_write') is not False
                or audit.get('period_start') != inputs.start.isoformat()
                or audit.get('period_end') != inputs.end.isoformat()
                or audit.get('grid_count') != len(inputs.gids)):
            raise InputBlocked('R02_PREPARED_AUDIT_MISMATCH')
        if set(r['gid'] for r in r02_prepared_input.counts_by_gid) != set(inputs.gids):
            raise InputBlocked('R02_AGGREGATION_GRID_MISMATCH')
        counts = list(r02_prepared_input.counts_by_gid)
    count_by_gid = {r['gid']: r for r in counts}
    incomplete = [r['gid'] for r in counts if r['classification_status'] != 'COMPLETE']
    if incomplete:
        raise InputBlocked('UNRESOLVED_COMPLAINTS_REQUIRE_EXPLICIT_EXCLUSION_POLICY:count=' + str(len(incomplete)))
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
    if r02_prepared_input is not None:
        contract['r02_explicit_exclusion_audit'] = dict(r02_prepared_input.audit)
    if r02_full_source_input is not None:
        contract['r02_full_source_audit'] = dict(r02_full_source_input.audit)
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
        setting_references=verified,
        source_audit_sha256=(r02_full_source_input.audit['audit_sha256']
                             if r02_full_source_input is not None else None),
        period_start=inputs.start, period_end=inputs.end,
    )
    if preview_only:
        from app.services.scoring.production_writer import plan
        from app.services.scoring.mysql_writer import _validate_evidence
        from app.services.scoring.d05_conditions import validate_d05_rule, verify_d05_persisted_conditions
        planned = plan(batch)
        _validate_evidence(batch, inputs.evidence_by_gid)
        rule = validate_d05_rule(document.get('d05_rule'))
        for candidate in candidates:
            verify_d05_persisted_conditions(candidate, rule)
        if r02_full_source_input is not None:
            from app.services.scoring.source_audit_lineage import verify_source_audit, verify_run_binding
            receipt = verify_source_audit(json.dumps(r02_full_source_input.audit).encode(),
                expected_sha256=batch.source_audit_sha256, start=inputs.start, end=inputs.end,
                grid_count=len(inputs.gids))
            runs = read_only('SELECT run_id,note FROM priority_run WHERE run_id=%s', (inputs.existing_run_id,))
            if len(runs) != 1:
                raise InputBlocked('D10_RUN_NOT_FOUND')
            verify_run_binding(inputs.existing_run_id, runs[0].get('note'), receipt)
        return {**planned, 'run_id':inputs.existing_run_id,
                'source_audit_sha256':batch.source_audit_sha256,
                'source_contract_sha256':_sha(contract), 'db_writes':0}
    written = write_approved_batch(batch,
        explicit_db_write_approval=explicit_db_write_approval,
        evidence_by_gid=inputs.evidence_by_gid,
        connection_factory=connection_factory,
        existing_run_id=inputs.existing_run_id)
    return {**written, 'setting_version_id': inputs.setting_version_id,
            'reviewed_complaint_count': len(reviewed_manifest),
            'complaint_count_in_period': sum(x['relevant_count'] for x in counts),
            'source_contract_sha256': _sha(contract)}
