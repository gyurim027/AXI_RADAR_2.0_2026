"""Atomic, explicitly approved MySQL 77/78/detail writer.

This module is a *persistence adapter*, not a scoring or approval engine. The
caller must prove input, policy, classification and setting provenance before
calling it; no endpoint automatically invokes this writer.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json

from app.services.priority.details import FIELDS, encode_evidence, store_evidence
from app.services.scoring.production_writer import OfficialBatch, ProductionBlocked, plan


def _validate_evidence(batch: OfficialBatch, evidence_by_gid: dict) -> None:
    if not isinstance(evidence_by_gid, dict):
        raise ProductionBlocked('DETAIL_EVIDENCE_REQUIRED')
    expected = {row['gid'] for row in batch.candidates}
    if set(evidence_by_gid) != expected:
        raise ProductionBlocked('DETAIL_GRID_SET_MISMATCH')
    for gid, detail in evidence_by_gid.items():
        if not isinstance(detail, dict) or set(detail) != set(FIELDS):
            raise ProductionBlocked('DETAIL_FIVE_FIELDS_REQUIRED')
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
        try:
            encode_evidence(1, gid, detail)  # format preflight; real run_id assigned in transaction
        except (ValueError, TypeError, OverflowError) as exc:
            raise ProductionBlocked('INVALID_DETAIL_EVIDENCE') from exc


def write_approved_batch(batch: OfficialBatch, *, explicit_db_write_approval: bool,
                         evidence_by_gid: dict | None = None, connection_factory=None) -> dict:
    """Write one approved run + candidates + all 5 evidence types atomically.

    Fail closed if sidecar evidence is missing. No DDL, no action (82) fabrication.
    `explicit_db_write_approval` is a per-batch human gate, not proof that an
    externally supplied approval record is authentic; upstream verification is
    mandatory. The approved setting row is independently checked under lock.
    """
    if explicit_db_write_approval is not True:
        raise ProductionBlocked('EXPLICIT_DB_WRITE_APPROVAL_REQUIRED')
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

            # Every scored GID must map to exactly one existing grid.
            for row in batch.candidates:
                cur.execute('SELECT ID_gid FROM grid_feature WHERE ID_gid=%s', (row['gid'],))
                if len(cur.fetchall()) != 1:
                    raise ProductionBlocked('GRID_ID_MISSING')

            token = 'official:' + metadata['fingerprint']
            cur.execute('SELECT run_id FROM priority_run WHERE note=%s FOR UPDATE', (token,))
            if cur.fetchall():
                raise ProductionBlocked('DUPLICATE_OFFICIAL_BATCH')
            cur.execute('INSERT INTO priority_run (build_id,rule_version,created_at,note) '
                        'VALUES (%s,%s,NOW(),%s)',
                        (batch.build_id, batch.rule_version, token))
            run_id = cur.lastrowid
            if not isinstance(run_id, int) or run_id <= 0:
                raise ProductionBlocked('RUN_ID_NOT_GENERATED')

            for row in batch.candidates:
                if row.get('note') not in (None, ''):
                    raise ProductionBlocked('CANDIDATE_NOTE_ALREADY_USED')
                cur.execute('INSERT INTO priority_candidate '
                            '(run_id,gid,selected_yn,score,rank_no,complaint_cnt,complaint_cnt_excl_low,'
                            'cond_result_yn,cond_hazard_yn,cond_exposure_yn,cond_vulnerable_yn,matched_roles,note) '
                            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                            (run_id, row['gid'], row.get('selected_yn'),
                             Decimal(str(row['official_score'])), row['rank_no'],
                             row['complaint_cnt'], row['complaint_cnt_excl_low'],
                             row.get('cond_result_yn'), row.get('cond_hazard_yn'),
                             row.get('cond_exposure_yn'), row.get('cond_vulnerable_yn'),
                             row.get('matched_roles'), store_evidence(run_id, row['gid'], evidence_by_gid[row['gid']])))

            cur.execute('SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s', (run_id,))
            actual = int(cur.fetchall()[0]['n'])
            if actual != metadata['candidate_count']:
                raise ProductionBlocked('SAVED_ROW_COUNT_MISMATCH')
            cur.execute("SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s AND note LIKE 'ev1:%%'", (run_id,))
            detail_count = int(cur.fetchall()[0]['n'])
            if detail_count != actual:
                raise ProductionBlocked('DETAIL_POINTER_COUNT_MISMATCH')
        con.commit()
        return {'run_id': run_id, 'candidate_count': actual, 'evidence_count': detail_count,
                'fingerprint': metadata['fingerprint'], 'status': 'WRITTEN'}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
