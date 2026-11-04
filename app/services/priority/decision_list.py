"""G-03 read-only persisted district decision list.

Never reads development process memory. Requires separately approved
radar_candidate_decision table and existing candidate/grid data.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.core import db

DISTRICTS = frozenset({'수정구', '중원구', '분당구'})
DECISIONS = frozenset({'우선 점검 대상', '제외', '보류'})
_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"


def table_ready(read=db.read_only) -> bool:
    rows = read(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        ('radar_candidate_decision',),
    )
    return bool(rows and int(rows[0]['n']) == 1)


def read_district_decisions(*, run_id: int, gu: str, decision: str | None,
                            limit: int, offset: int, read=db.read_only) -> dict:
    """Read only; authoritative gu is from grid_feature, not decision.gu."""
    if gu not in DISTRICTS:
        raise ValueError('invalid_gu')
    if decision is not None and decision not in DECISIONS:
        raise ValueError('invalid_decision')
    if not 1 <= limit <= 500 or offset < 0 or run_id <= 1:
        raise ValueError('invalid_pagination_or_run')
    if not table_ready(read):
        raise LookupError('decision_schema_unavailable')
    # Join to actual candidate prevents stale/mislinked decisions from leaking.
    base = (
        " FROM radar_candidate_decision d "
        "JOIN priority_candidate c ON c.run_id=d.run_id AND c.gid=d.gid "
        "JOIN grid_feature f ON f.ID_gid=c.gid "
        f"WHERE d.run_id=%s AND {_GU}=%s "
        f"AND d.gu={_GU} "
    )
    args: list = [run_id, gu]
    if decision is not None:
        base += ' AND d.decision=%s '
        args.append(decision)
    totals = read('SELECT COUNT(*) AS n' + base, args)
    total = int(totals[0]['n']) if totals else 0
    counts = read(
        'SELECT d.decision AS choice, COUNT(*) AS n' +
        base + ' GROUP BY d.decision', args
    )
    by_decision = {name: 0 for name in ('우선 점검 대상', '제외', '보류')}
    for row in counts:
        if row['choice'] in by_decision:
            by_decision[row['choice']] = int(row['n'])
    rows = read(
        'SELECT d.run_id, d.gid, d.decision, d.reason_code, d.reason_text, '
        'd.memo, d.rule_version, d.decided_by, d.decided_at, d.revision, '
        f'{_GU} AS gu, c.selected_yn, c.score, c.rank_no ' +
        base + ' ORDER BY c.rank_no IS NULL, c.rank_no, d.gid LIMIT %s OFFSET %s',
        [*args, limit, offset],
    )

    def serial(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    return {
        'runId': run_id, 'gu': gu, 'total': total, 'limit': limit, 'offset': offset,
        'counts': by_decision, 'storage': 'operational_db',
        'decisions': [{
            'runId': int(r['run_id']), 'gid': r['gid'], 'gu': r['gu'],
            'decision': r['decision'], 'reasonCode': r['reason_code'],
            'reasonText': r['reason_text'], 'memo': r['memo'],
            'ruleVersion': r['rule_version'], 'decidedBy': r['decided_by'],
            'decidedAt': serial(r['decided_at']), 'revision': r['revision'],
            'selectedYn': r['selected_yn'], 'score': serial(r['score']),
            'rankNo': r['rank_no'],
        } for r in rows],
    }
