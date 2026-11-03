"""D-10 persisted run workflow. Does not modify scoring tables.

Requires separately approved schema: radar_run_workflow, radar_run_status_event.
Existing app.core.db is responsible for connection lifecycle and rollback.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from app.core import db

WORKFLOW_TABLES = ('radar_run_workflow', 'radar_run_status_event')
VALID_KINDS = frozenset({'연간', '반기 참고'})


class WorkflowError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _id(value: Any) -> int:
    if type(value) is not int or value <= 1:
        # Run 1 is a preserved historical prototype, not an operable round.
        raise WorkflowError(422, 'invalid_operational_run', '운영 가능한 실행 회차 번호가 아닙니다.')
    return value


def _clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise WorkflowError(422, 'invalid_run_name', '회차명이 필요합니다.')
    value = name.strip()
    if len(value) > 100:
        raise WorkflowError(422, 'invalid_run_name', '회차명은 100자 이하입니다.')
    return value


def tables_ready() -> bool:
    """Only metadata SELECT; safe to call before approved migration is applied."""
    rows = db.read_only(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s)", WORKFLOW_TABLES
    )
    return bool(rows and int(rows[0]['n']) == len(WORKFLOW_TABLES))


def metadata_for_runs(run_ids: list[int]) -> dict[int, dict]:
    """Return verified persisted values, or {} prior to schema installation."""
    if not run_ids or not tables_ready():
        return {}
    ids = [int(x) for x in dict.fromkeys(run_ids)]
    placeholders = ','.join(['%s'] * len(ids))
    rows = db.read_only(
        "SELECT run_id, run_name, run_kind, run_status, opened_at "
        f"FROM radar_run_workflow WHERE run_id IN ({placeholders})", ids
    )
    return {
        int(row['run_id']): {
            'name': row['run_name'], 'kind': row['run_kind'],
            'status': row['run_status'], 'opened_at': row['opened_at'],
        }
        for row in rows
    }


def open_run(*, run_id: int, name: str, kind: str, actor_id: int) -> dict:
    """Open annual as 검토 중 or half-year as 참고. Atomic and retry-safe.

    Scoring completion gate: require at least one candidate, all candidates scored.
    The decision to open is explicit and made by an authenticated operator.
    """
    _id(run_id)
    name = _clean_name(name)
    if kind not in VALID_KINDS:
        raise WorkflowError(422, 'invalid_run_kind', '회차 종류는 연간 또는 반기 참고여야 합니다.')
    if type(actor_id) is not int or actor_id <= 0:
        raise WorkflowError(403, 'invalid_operator_identity', '로그인한 운영자 식별값을 확인할 수 없습니다.')
    if not tables_ready():
        raise WorkflowError(503, 'workflow_schema_unavailable', '운영 회차 저장 테이블이 아직 적용되지 않았습니다.')

    target = '검토 중' if kind == '연간' else '참고'
    with db.connect() as con:
        with con.cursor() as cur:
            # Serializes competing opens of the same run and respects existing DB77 row.
            cur.execute("SELECT run_id FROM priority_run WHERE run_id=%s FOR UPDATE", (run_id,))
            if cur.fetchone() is None:
                raise WorkflowError(404, 'run_not_found', '실행 회차를 찾을 수 없습니다.')
            cur.execute(
                "SELECT run_name, run_kind, run_status, opened_at "
                "FROM radar_run_workflow WHERE run_id=%s FOR UPDATE", (run_id,)
            )
            prior = cur.fetchone()
            if prior is not None:
                if (prior['run_name'], prior['run_kind'], prior['run_status']) == (name, kind, target):
                    # Exact replay is a no-op, not a second event.
                    return {'run_id': run_id, 'status': target, 'name': name,
                            'kind': kind, 'opened_at': prior['opened_at'], 'already_open': True}
                raise WorkflowError(409, 'run_already_open', '이미 개시된 회차의 종류·상태·이름은 이 API에서 변경할 수 없습니다.')
            cur.execute(
                "SELECT COUNT(*) AS candidate_count, "
                "SUM(score IS NOT NULL) AS scored_count "
                "FROM priority_candidate WHERE run_id=%s", (run_id,)
            )
            counts = cur.fetchone()
            count = int(counts['candidate_count'] or 0)
            scored = int(counts['scored_count'] or 0)
            if not count or scored != count:
                raise WorkflowError(409, 'scoring_not_complete',
                                    f'산정 결과 확인이 필요합니다. 후보 {count}건, 점수 산출 {scored}건.')
            cur.execute("SELECT NOW(6) AS now_value")
            opened_at = cur.fetchone()['now_value']
            cur.execute(
                "INSERT INTO radar_run_workflow "
                "(run_id,run_name,run_kind,run_status,opened_at,opened_by) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (run_id, name, kind, target, opened_at, actor_id)
            )
            cur.execute(
                "INSERT INTO radar_run_status_event "
                "(run_id,from_status,to_status,actor_ref,event_reason) "
                "VALUES (%s,%s,%s,%s,%s)",
                (run_id, None, target, actor_id, 'D10_OPERATOR_OPEN')
            )
        con.commit()
    return {'run_id': run_id, 'status': target, 'name': name,
            'kind': kind, 'opened_at': opened_at, 'already_open': False}
