"""DB62 three-kind proposal transaction. Never approves or starts calculation."""
from __future__ import annotations
import os
from pathlib import Path
from app.core import db, access_audit as audit
from app.core.responses import ApiError
from app.services.scoring.policy_preflight import (
    preflight_policy, store_policy_evidence)
from app.services.scoring.setting_links import KINDS, SettingLinksBlocked
from app.services.settings.repository import COLUMNS

MAX_POLICY_BYTES = 131072


def evidence_directory():
    value = os.environ.get('RADAR_POLICY_EVIDENCE_DIR', '').strip()
    if not value or not Path(value).is_absolute():
        raise ApiError(503, 'policy_evidence_storage_not_configured',
                       '서버의 정책 근거 보관 경로를 설정해 주세요')
    return Path(value)


def validate_proposal(policy_document, expected_sha256):
    if not isinstance(policy_document, str):
        raise ApiError(422, 'invalid_policy_document', '정책 원문 문자열이 필요합니다')
    try:
        raw = policy_document.encode('utf-8')
        if len(raw) > MAX_POLICY_BYTES:
            raise ApiError(413, 'policy_document_too_large', '정책 문서가 너무 큽니다')
        report = preflight_policy(raw, expected_sha256=expected_sha256)
        label = report['version_label']
        if not isinstance(label, str) or not label.strip() or len(label) > 100:
            raise ApiError(422, 'invalid_policy_label', '정책 판본 이름을 확인해 주세요')
        return raw, report
    except ApiError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, SettingLinksBlocked):
        raise ApiError(422, 'policy_evidence_invalid',
                       '정책 원문 해시·설정 구성요소·결측 규칙을 확인해 주세요') from None


def _operator(user):
    uid = user.get('user_id')
    if user.get('role') != 'operator':
        raise ApiError(403, 'forbidden_role', '운영자만 산정 설정을 제안할 수 있습니다')
    if type(uid) is not int or not 0 < uid <= 9223372036854775807:
        raise ApiError(403, 'invalid_actor', '로그인 사용자를 확인해 주세요')
    return uid


def _ordered_bundle(rows, report, *, new_actor=None):
    by_kind = {kind: [r for r in rows if r['setting_kind'] == kind] for kind in KINDS}
    if len(rows) != 3 or any(len(v) != 1 for v in by_kind.values()):
        raise ApiError(409, 'proposal_bundle_incomplete_or_ambiguous',
                       '같은 문서의 설정 묶음이 불완전하거나 중복입니다. 기존 제안을 확인해 주세요')
    ordered = [by_kind[k][0] for k in KINDS]
    ids = [r['setting_version_id'] for r in ordered]
    if any(type(i) is not int or i <= 1 or i > 9223372036854775807 for i in ids) or len(set(ids)) != 3:
        raise ApiError(409, 'proposal_ids_invalid', '설정 식별자를 확인해 주세요')
    actors = {r['proposed_by'] for r in ordered}
    if (len(actors) != 1 or None in actors or
            (new_actor is not None and actors != {new_actor})):
        raise ApiError(409, 'proposal_bundle_actor_mismatch', '제안 묶음의 생성자를 확인해 주세요')
    for row in ordered:
        if (row['version_label'] != report['version_label'] or
                row['content_ref'] != report['official_content_ref'] or
                not row['proposed_at']):
            raise ApiError(409, 'proposal_bundle_identity_mismatch', '기존 제안의 원문·판본을 확인해 주세요')
        status = row['approval_status']
        if status == '돌려보냄':
            raise ApiError(409, 'proposal_previously_returned', '돌려보낸 제안입니다. 검토 의견에 따라 문서를 보완해 주세요')
        if status not in ('제안', '승인'):
            raise ApiError(409, 'proposal_status_invalid', '기존 제안 상태를 확인해 주세요')
        if status == '승인' and (not row['approved_by'] or not row['approved_at']):
            raise ApiError(409, 'proposal_approval_incomplete', '기존 승인 근거를 확인해 주세요')
        if status == '제안' and (row['approved_by'] is not None or row['approved_at'] is not None):
            raise ApiError(409, 'proposal_pending_state_invalid', '제안 상태와 승인 근거가 일치하지 않습니다')
        if new_actor is not None and status != '제안':
            raise ApiError(409, 'proposal_insert_state_invalid', '새 제안의 저장 상태를 확인해 주세요')
    return ordered


class SettingsProposalRepository:
    def preflight(self, policy_document, expected_sha256, user):
        _operator(user)
        _, report = validate_proposal(policy_document, expected_sha256)
        return {'validation': report, 'proposed_kinds': list(KINDS),
                'proposal_created': False, 'approval_created': False,
                'scoring_authorized': False, 'recalculation_started': False}

    def propose(self, policy_document, expected_sha256, request, user):
        uid = _operator(user)
        raw, report = validate_proposal(policy_document, expected_sha256)
        root = evidence_directory()
        # One advisory lock per full document identity; no DDL/unique index needed.
        lock_name = 'db62p:' + report['raw_sha256'][:58]
        with db.connect() as con:
            acquired = False
            try:
                with con.cursor() as cur:
                    cur.execute('SELECT GET_LOCK(%s, 5) AS acquired', (lock_name,))
                    lock = cur.fetchone()
                    if not lock or lock['acquired'] != 1:
                        raise ApiError(503, 'proposal_lock_busy', '같은 문서의 제안 처리 중입니다. 잠시 후 확인해 주세요')
                    acquired = True
                    try:
                        store_policy_evidence(raw, root, expected_sha256=report['raw_sha256'])
                    except (ValueError, TypeError, KeyError, OSError, SettingLinksBlocked):
                        raise ApiError(503, 'policy_evidence_storage_failed', '정책 근거 저장·재읽기를 확인해 주세요') from None
                    # Lock rows as well; I07 may independently be reviewing them.
                    cur.execute(f'SELECT {COLUMNS} FROM setting_version WHERE content_ref=%s '
                                'AND setting_kind IN (%s,%s,%s) ORDER BY setting_version_id FOR UPDATE',
                                (report['official_content_ref'], *KINDS))
                    existing = cur.fetchall()
                    if existing:
                        ordered = _ordered_bundle(existing, report)
                        already_exists = True
                    else:
                        cur.execute("SELECT TABLE_NAME AS table_name,ENGINE AS engine FROM INFORMATION_SCHEMA.TABLES "
                                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('setting_version','access_audit')")
                        engines={r['table_name']:str(r['engine']).upper() for r in cur.fetchall()}
                        if any(engines.get(t) != 'INNODB' for t in ('setting_version','access_audit')):
                            raise ApiError(503, 'proposal_transaction_engine_required',
                                           '설정·감사 표의 거래 저장 지원을 확인해 주세요')
                        ids = []
                        for kind in KINDS:
                            cur.execute('INSERT INTO setting_version '
                                '(setting_kind,version_label,content_ref,proposed_by,proposed_at,approval_status) '
                                'VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP,%s)',
                                (kind, report['version_label'], report['official_content_ref'], uid, '제안'))
                            ids.append(cur.lastrowid)
                        if len(set(ids)) != 3 or any(type(i) is not int or i <= 1 for i in ids):
                            raise ApiError(409, 'proposal_ids_invalid', '서로 다른 신규 설정 식별자가 필요합니다')
                        for sid, kind in zip(ids, KINDS):
                            audit.record(request, user, audit.SETTING_CHANGE,
                                key=f'setting_version:{sid}', reason=f'산정 설정 제안: {kind}', connection=con)
                        cur.execute(f'SELECT {COLUMNS} FROM setting_version '
                                    'WHERE setting_version_id IN (%s,%s,%s)', tuple(ids))
                        ordered = _ordered_bundle(cur.fetchall(), report, new_actor=uid)
                        if [r['setting_version_id'] for r in ordered] != ids:
                            raise ApiError(409, 'proposal_readback_ids_changed', '저장된 설정 식별자가 일치하지 않습니다')
                        already_exists = False
                # Release rows before returning/releasing the advisory lock.
                try:
                    con.commit()
                except Exception:
                    # A lost commit response is not proof of rollback. Same request
                    # can be checked again using the hash identity, never auto-approved.
                    raise ApiError(503, 'proposal_commit_unconfirmed',
                                   '저장 결과를 확인하지 못했습니다. 같은 문서로 다시 확인해 주세요') from None
            finally:
                if acquired:
                    try:
                        with con.cursor() as cur:
                            cur.execute('SELECT RELEASE_LOCK(%s) AS released', (lock_name,))
                    except Exception:
                        pass  # Connection close also releases MySQL advisory locks.
        ids = [r['setting_version_id'] for r in ordered]
        return {'proposals': ordered, 'already_exists': already_exists,
                'setting_version_ids': dict(zip(('weight', 'threshold', 'priority_condition'), ids)),
                'review_urls': [f'/api/approvals/{i}/review' for i in ids],
                'all_approved': all(r['approval_status'] == '승인' for r in ordered),
                'proposal_created': not already_exists, 'approval_created': False,
                'scoring_authorized': False, 'official_run_created': False,
                'recalculation_started': False}


def get_repository():
    return SettingsProposalRepository()
