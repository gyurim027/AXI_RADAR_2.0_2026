"""Atomic, explicitly approved MySQL 77/78/detail writer.

This module is a *persistence adapter*, not a scoring or approval engine. The
caller must prove input, policy, classification and setting provenance before
calling it; no endpoint automatically invokes this writer.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json

from app.services.priority.db8_details import COLS as DB8_COLS, db8_params, assert_db8_columns

from app.services.priority.details import FIELDS, encode_evidence
from app.services.scoring.production_writer import OfficialBatch, ProductionBlocked, plan
from app.services.scoring.setting_links import links_enabled, verify_locked_references, FIELDS as SETTING_FIELDS


def _validate_evidence(batch: OfficialBatch, evidence_by_gid: dict) -> None:
    if not isinstance(evidence_by_gid, dict):
        raise ProductionBlocked('DETAIL_EVIDENCE_REQUIRED')
    expected = {row['gid'] for row in batch.candidates}
    if set(evidence_by_gid) != expected:
        raise ProductionBlocked('DETAIL_GRID_SET_MISMATCH')
    for gid, detail in evidence_by_gid.items():
        if not isinstance(detail, dict) or set(detail) != set(FIELDS):
            raise ProductionBlocked('DETAIL_EIGHT_FIELDS_REQUIRED')
        if not isinstance(detail['domain_scores'], dict) or not detail['domain_scores']:
            raise ProductionBlocked('DETAIL_DOMAIN_SCORES_MISSING')
        if not isinstance(detail['indicator_contributions'], dict) or not detail['indicator_contributions']:
            raise ProductionBlocked('DETAIL_INDICATORS_MISSING')
        if not isinstance(detail['unevaluated_reasons'], (dict, list)):
            raise ProductionBlocked('DETAIL_UNEVALUATED_REASONS_MISSING')
        if not isinstance(detail['confidence_grade'], str) or not detail['confidence_grade'].strip():
            raise ProductionBlocked('DETAIL_CONFIDENCE_MISSING')
        if detail['score_excluding_accidents'] is None:
            raise ProductionBlocked('DETAIL_ACCIDENT_EXCLUDED_SCORE_MISSING')
        if not isinstance(detail['exclusion_reasons'], (list, dict)):
            raise ProductionBlocked('DETAIL_EXCLUSION_REASONS_MISSING')
        if detail['complaint_contribution'] is None:
            raise ProductionBlocked('DETAIL_COMPLAINT_CONTRIBUTION_MISSING')
        if not isinstance(detail['policy_version'], str) or not detail['policy_version'].strip():
            raise ProductionBlocked('DETAIL_POLICY_VERSION_MISSING')
        if detail['policy_version'] != batch.rule_version:
            raise ProductionBlocked('DETAIL_POLICY_VERSION_MISMATCH')
        try:
            encode_evidence(1, gid, detail)  # pure format validation
            db8_params(detail)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ProductionBlocked('INVALID_DETAIL_EVIDENCE') from exc


def write_approved_batch(batch: OfficialBatch, *, explicit_db_write_approval: bool,
                         evidence_by_gid: dict | None = None, connection_factory=None, existing_run_id: int | None = None) -> dict:
    """Write all eight DB78 detail fields for an existing D-10 run atomically.

    Fail closed if DB78 detail columns or values are missing. No DDL, no action (82) fabrication.
    `explicit_db_write_approval` is a per-batch human gate, not proof that an
    externally supplied approval record is authentic; upstream verification is
    mandatory. The approved setting row is independently checked under lock.
    """
    if type(existing_run_id) is not int or existing_run_id <= 0:
        raise ProductionBlocked('D10_EXISTING_RUN_ID_REQUIRED')
    # Existing run 1 is retained for historical reads only, never for new official writes.
    if existing_run_id == 1:
        raise ProductionBlocked('LEGACY_RUN1_OFFICIAL_WRITE_BLOCKED')
    if explicit_db_write_approval is not True:
        raise ProductionBlocked('EXPLICIT_DB_WRITE_APPROVAL_REQUIRED')
    if batch.setting_version_id == 1:
        raise ProductionBlocked('INTERNAL_DEMO_SIMULATION_CANNOT_WRITE_OFFICIAL_77_78')
    if not links_enabled():
        raise ProductionBlocked('DB77_V24_ACTIVATION_REQUIRED')
    metadata = plan(batch)
    _validate_evidence(batch, evidence_by_gid)
    evidence_hashes = {gid: encode_evidence(1, gid, data)[1] for gid, data in evidence_by_gid.items()}
    metadata['fingerprint'] = sha256(json.dumps({'batch':metadata['fingerprint'],
        'details':evidence_hashes}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if connection_factory is None:
        from app.core.db import raw_connection
        connection_factory = raw_connection

    con = connection_factory()
    try:
        with con.cursor() as cur:
            native_mode = batch.build_id.startswith('db59:')
            if native_mode:
                from app.services.scoring.input_builds import _begin
                _begin(cur)
                from app.services.scoring.input_builds import verify_execution_build
                try:
                    proof=verify_execution_build(cur,build_id=batch.build_id,policy_sha256=batch.policy_digest,
                        setting_ids=tuple(r.setting_version_id for r in batch.setting_references),
                        start=batch.period_start,end=batch.period_end)
                except ValueError as exc:
                    raise ProductionBlocked('NATIVE_BUILD_EXECUTION_NOT_VERIFIED:'+str(exc)) from exc
            verify_locked_references(cur, batch.setting_references)
            cur.execute('SELECT setting_version_id, version_label, content_ref, approval_status, approved_at '
                        'FROM setting_version WHERE setting_version_id=%s FOR UPDATE',
                        (batch.setting_version_id,))
            settings = cur.fetchall()
            if len(settings) != 1:
                raise ProductionBlocked('SETTING_NOT_FOUND')
            setting = settings[0]
            if (setting.get('approval_status') not in ('승인', 'APPROVED')
                or setting.get('approved_at') is None):
                raise ProductionBlocked('SETTING_NOT_APPROVED')
            if setting.get('content_ref') != batch.setting_content_ref:
                raise ProductionBlocked('SETTING_CONTENT_MISMATCH')
            if setting.get('version_label') != batch.rule_version:
                raise ProductionBlocked('RULE_VERSION_MISMATCH')

            try: assert_db8_columns(cur)
            except ValueError as exc: raise ProductionBlocked(str(exc)) from exc

            # Every scored GID must map to exactly one existing grid.
            for row in batch.candidates:
                cur.execute('SELECT ID_gid FROM grid_feature WHERE ID_gid=%s', (row['gid'],))
                if len(cur.fetchall()) != 1:
                    raise ProductionBlocked('GRID_ID_MISSING')

            # D-10 owns run creation. Never invent or allocate a run in the scorer.
            run_id = existing_run_id
            cur.execute('SELECT run_id,build_id,rule_version,note,period_start,period_end,'+
                        ','.join(SETTING_FIELDS)+' FROM priority_run WHERE run_id=%s FOR UPDATE',
                        (run_id,))
            existing = cur.fetchall()
            if len(existing) != 1:
                raise ProductionBlocked('D10_RUN_NOT_FOUND')
            saved_run = existing[0]
            if batch.source_audit_sha256 is not None:
                from app.services.scoring.source_audit_lineage import source_audit_note
                if saved_run.get('note') != source_audit_note(batch.source_audit_sha256):
                    raise ProductionBlocked('D10_RUN_SOURCE_AUDIT_MISMATCH')
            if saved_run.get('build_id') != batch.build_id or saved_run.get('rule_version') != batch.rule_version:
                raise ProductionBlocked('D10_RUN_BUILD_OR_RULE_MISMATCH')
            if saved_run.get('period_start') != batch.period_start or saved_run.get('period_end') != batch.period_end:
                raise ProductionBlocked('D10_RUN_PERIOD_MISMATCH')
            if tuple(saved_run.get(f) for f in SETTING_FIELDS) != tuple(r.setting_version_id for r in batch.setting_references):
                raise ProductionBlocked('D10_RUN_SETTING_MISMATCH')
            if native_mode:
                if batch.source_audit_sha256 != proof['source_audit_sha256']:
                    raise ProductionBlocked('NATIVE_BATCH_AUDIT_MISMATCH')
                counts={r['gid']:r for r in proof['counts_by_gid']}
                if set(counts)!={r['gid'] for r in batch.candidates}:
                    raise ProductionBlocked('NATIVE_BATCH_GRID_POPULATION_MISMATCH')
                for candidate in batch.candidates:
                    actual=counts[candidate['gid']]
                    if (candidate['complaint_cnt']!=actual['relevant_count'] or
                            candidate['complaint_cnt_excl_low']!=actual['count_excl_low']):
                        raise ProductionBlocked('NATIVE_BATCH_COMPLAINT_COUNTS_MISMATCH')
            cur.execute('SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s FOR UPDATE', (run_id,))
            if int(cur.fetchall()[0]['n']) != 0:
                raise ProductionBlocked('D10_RUN_ALREADY_HAS_CANDIDATES')

            for row in batch.candidates:
                if row.get('note') not in (None, ''):
                    raise ProductionBlocked('CANDIDATE_NOTE_ALREADY_USED')
                base_cols=('run_id','gid','selected_yn','score','rank_no','complaint_cnt',
                           'complaint_cnt_excl_low','cond_result_yn','cond_hazard_yn',
                           'cond_exposure_yn','cond_vulnerable_yn','matched_roles','note')
                values=(run_id, row['gid'], row.get('selected_yn'),
                        Decimal(str(row['official_score'])), row['rank_no'],
                        row['complaint_cnt'], row['complaint_cnt_excl_low'],
                        row.get('cond_result_yn'), row.get('cond_hazard_yn'),
                        row.get('cond_exposure_yn'), row.get('cond_vulnerable_yn'),
                        row.get('matched_roles'), None)
                values += db8_params(evidence_by_gid[row['gid']])
                cols=base_cols+DB8_COLS
                cur.execute('INSERT INTO priority_candidate ('+','.join(cols)+') VALUES ('+
                            ','.join(['%s']*len(cols))+')',values)

            cur.execute('SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s', (run_id,))
            actual = int(cur.fetchall()[0]['n'])
            if actual != metadata['candidate_count']:
                raise ProductionBlocked('SAVED_ROW_COUNT_MISMATCH')
            cur.execute('SELECT gid,'+','.join(DB8_COLS)+' FROM priority_candidate WHERE run_id=%s', (run_id,))
            from app.services.priority.db8_details import decode_db_row
            saved=cur.fetchall()
            if len(saved)!=actual or {r['gid'] for r in saved}!=set(evidence_by_gid):
                raise ProductionBlocked('SAVED_DETAIL_GRID_SET_MISMATCH')
            for r in saved:
                detail=decode_db_row(r)
                if db8_params({k:detail[k] for k in FIELDS})!=db8_params(evidence_by_gid[r['gid']]):
                    raise ProductionBlocked('SAVED_DETAIL_VALUE_MISMATCH')
            detail_count=len(saved)
            cur.execute('SELECT period_start,period_end,'+','.join(SETTING_FIELDS)+
                        ' FROM priority_run WHERE run_id=%s',(run_id,))
            runs=cur.fetchall()
            if (len(runs)!=1 or runs[0].get('period_start')!=batch.period_start
                    or runs[0].get('period_end')!=batch.period_end
                    or tuple(runs[0].get(f) for f in SETTING_FIELDS)!=tuple(r.setting_version_id for r in batch.setting_references)):
                raise ProductionBlocked('SAVED_RUN_SETTING_OR_PERIOD_MISMATCH')
        con.commit()
        return {'run_id': run_id, 'candidate_count': actual, 'evidence_count': detail_count,
                'fingerprint': metadata['fingerprint'], 'status': 'WRITTEN'}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
