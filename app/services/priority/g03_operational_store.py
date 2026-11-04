"""G-03 operational persistence adapter for the *approved* RADAR workflow schema.

Never creates/changes schema. Caller must authenticate, verify jurisdiction and
validate reason with existing G-03 API. Guarded by RADAR_G03_PERSIST_ENABLED.
Requires 4 approved tables and only operates on annual runs in 검토 중 state.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from app.core import db

TABLES = ('radar_run_workflow', 'radar_candidate_decision',
          'radar_decision_event', 'radar_district_confirmation')
DISTRICTS = frozenset({'수정구', '중원구', '분당구'})
DECISIONS = frozenset({'우선 점검 대상', '제외', '보류'})
_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"

class OperationalError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    return os.getenv('RADAR_G03_PERSIST_ENABLED') == '1'


def schema_ready(read=None) -> bool:
    read = read or db.read_only
    p = ','.join(['%s'] * len(TABLES))
    rows = read('SELECT COUNT(*) AS n FROM information_schema.TABLES '
                f'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ({p})', TABLES)
    return bool(rows and int(rows[0]['n']) == len(TABLES))


def _ensure_ready() -> None:
    if not enabled():
        raise OperationalError(503, '운영 G-03 저장 기능이 활성화되지 않았습니다')
    if not schema_ready():
        raise OperationalError(503, 'G-03 운영 저장 테이블이 아직 준비되지 않았습니다')


def create_decision(*, run_id: int, gid: str, gu: str, decision: str,
                    reason_code: str | None, reason_text: str | None,
                    memo: str, actor_id: int, rule_version: str) -> dict[str, Any]:
    """Atomic first decision + CREATE audit event; no scoring-table mutation.

    A caller must already perform FastAPI authentication, role/gu and reason
    validation. The transaction rechecks authoritative candidate/gu and state.
    """
    if type(run_id) is not int or run_id <= 1 or not isinstance(gid, str) or not gid.strip():
        raise OperationalError(422, '회차 또는 격자 식별값을 확인할 수 없습니다')
    if gu not in DISTRICTS or decision not in DECISIONS:
        raise OperationalError(422, '관할 또는 결정값을 확인할 수 없습니다')
    if type(actor_id) is not int or actor_id <= 0:
        raise OperationalError(403, '인증된 결정자 식별값이 없습니다')
    if not isinstance(rule_version, str) or not rule_version.strip():
        raise OperationalError(409, '산정 규칙 버전이 확인되지 않았습니다')
    _ensure_ready()
    with db.connect() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT r.run_id, r.rule_version, w.run_kind, w.run_status '
                            'FROM priority_run r JOIN radar_run_workflow w ON w.run_id=r.run_id '
                            'WHERE r.run_id=%s FOR UPDATE', (run_id,))
                workflow = cur.fetchone()
                if workflow is None or workflow['run_kind'] != '연간' or workflow['run_status'] != '검토 중':
                    raise OperationalError(409, '검토 중인 연간 회차에만 결정을 등록할 수 있습니다')
                if workflow['rule_version'] != rule_version:
                    raise OperationalError(409, '요청 당시의 규칙 버전이 변경됐습니다')
                cur.execute('SELECT c.run_id, c.gid, '
                            f'{_GU} AS gu FROM priority_candidate c '
                            'LEFT JOIN grid_feature f ON f.ID_gid=c.gid '
                            'WHERE c.run_id=%s AND c.gid=%s FOR UPDATE', (run_id, gid))
                row = cur.fetchone()
                if row is None:
                    raise OperationalError(404, '해당 회차의 후보 격자가 없습니다')
                if row['gu'] != gu:
                    raise OperationalError(403, '결정 대상의 관할 구가 일치하지 않습니다')
                cur.execute('SELECT 1 FROM radar_district_confirmation '
                            'WHERE run_id=%s AND gu=%s FOR UPDATE', (run_id, gu))
                if cur.fetchone() is not None:
                    raise OperationalError(409, '이미 확정된 구에는 결정을 등록할 수 없습니다')
                cur.execute('SELECT 1 FROM radar_candidate_decision WHERE run_id=%s AND gid=%s FOR UPDATE',
                            (run_id, gid))
                if cur.fetchone() is not None:
                    raise OperationalError(409, '최초 결정이 이미 존재합니다. 변경은 G-04에서 처리해야 합니다')
                cur.execute('INSERT INTO radar_candidate_decision '
                            '(run_id,gid,gu,decision,reason_code,reason_text,memo,rule_version,decided_by,revision) '
                            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)',
                            (run_id, gid, gu, decision, reason_code, reason_text,
                             memo, rule_version, actor_id))
                # Exact event payload written in same transaction as the current decision.
                import json
                after = json.dumps({'decision': decision, 'reason_code': reason_code,
                                    'reason_text': reason_text, 'memo': memo}, ensure_ascii=False)
                cur.execute('INSERT INTO radar_decision_event '
                            '(run_id,gid,revision,event_kind,before_json,after_json,change_reason,actor_ref) '
                            'VALUES (%s,%s,1,%s,NULL,%s,NULL,%s)',
                            (run_id, gid, 'CREATE', after, actor_id))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {'run_id': run_id, 'gid': gid, 'gu': gu, 'decision': decision,
            'reason_code': reason_code, 'reason_text': reason_text,
            'storage': 'operational_db', 'operational_saved': True}


def list_decisions(*, run_id: int, user: dict, read=None) -> dict:
    """G-03 frontend contract, only decided rows, scoped by verified server role."""
    if type(run_id) is not int or run_id < 1:
        raise OperationalError(422, '유효한 회차가 아닙니다')
    role = user.get('role')
    if role == 'district':
        from app.core.auth import allowed_gus
        gus = set(allowed_gus(user)) & DISTRICTS
        if not gus:
            raise OperationalError(403, '조회 가능한 담당 구가 없습니다')
    elif role == 'city':
        gus = DISTRICTS
    else:
        raise OperationalError(403, '조회 권한이 없습니다')
    _ensure_ready()
    read = read or db.read_only
    # No unbounded records; cursor paging is a future extension; this is the
    # current front contract and deliberately caps output instead of truncating.
    places = ','.join(['%s'] * len(gus))
    base = ('FROM radar_candidate_decision d '
            'JOIN priority_candidate c ON c.run_id=d.run_id AND c.gid=d.gid '
            'JOIN grid_feature f ON f.ID_gid=c.gid '
            f'WHERE d.run_id=%s AND {_GU} IN ({places}) AND d.gu={_GU}')
    args = [run_id, *sorted(gus)]
    nrows = read('SELECT COUNT(*) AS n ' + base, args)
    total = int(nrows[0]['n']) if nrows else 0
    if total > 5000:
        raise OperationalError(409, '목록이 5,000건을 초과합니다. 페이지 조회 계약이 필요합니다')
    rows = read('SELECT d.gid, d.decision, d.reason_code, d.reason_text, d.decided_at '
                + base + ' ORDER BY d.gid', args)
    output = []
    for r in rows:
        dt = r.get('decided_at')
        if isinstance(dt, (date, datetime)):
            dt = dt.isoformat()
        result = {'gid': r['gid'], 'decision': r['decision'],
                  'reason_code': r['reason_code'], 'decided_at': dt}
        if r['reason_code'] == '기타':
            result['reason_text'] = r.get('reason_text')
        output.append(result)
    return {'run_id': run_id, 'decisions': output,
            'storage': 'operational_db', 'operational_saved': True}


def get_decision(*, run_id: int, gid: str, gu: str, read=None) -> dict | None:
    """Read single persisted record; caller already checked same-district access."""
    if gu not in DISTRICTS:
        raise OperationalError(403, '담당 구를 확인할 수 없습니다')
    _ensure_ready()
    read = read or db.read_only
    rows = read('SELECT d.run_id, d.gid, d.gu, d.decision, d.reason_code, '
                'd.reason_text, d.memo, d.rule_version, d.decided_by, d.decided_at, d.revision '
                'FROM radar_candidate_decision d '
                'JOIN priority_candidate c ON c.run_id=d.run_id AND c.gid=d.gid '
                'JOIN grid_feature f ON f.ID_gid=c.gid '
                f'WHERE d.run_id=%s AND d.gid=%s AND d.gu=%s AND {_GU}=%s',
                (run_id, gid, gu, gu))
    return rows[0] if rows else None
