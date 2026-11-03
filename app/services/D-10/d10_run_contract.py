"""D-10 read-only run response contract.

Compatibility adapter for the v2.4 priority_run table.  The table does not
contain name/kind/status/opened_at.  Never fabricate those values from
candidate counts, run IDs, or a successful calculation.

This is a standalone helper: importing it does not access the DB.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

VALID_STATUS = frozenset({'산정 중', '검토 중', '확정', '참고'})
VALID_KIND = frozenset({'연간', '반기 참고'})
REQUIRED = ('status', 'name', 'kind', 'opened_at')


def _iso(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def to_run_response(row: Mapping[str, Any], metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a DB77 row.  Metadata must be verified persisted state.

    A mapping supplied by an untrusted client or a mock is NOT a valid source.
    Callers are responsible for loading/validating operational metadata.
    """
    metadata = metadata or {}
    status = metadata.get('status')
    kind = metadata.get('kind')
    if status is not None and status not in VALID_STATUS:
        raise ValueError('Unrecognized run status')
    if kind is not None and kind not in VALID_KIND:
        raise ValueError('Unrecognized run kind')
    opened_at = metadata.get('opened_at')
    if opened_at is not None and not isinstance(opened_at, (str, date, datetime)):
        raise ValueError('Invalid opened_at')
    name = metadata.get('name')
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError('Invalid run name')
    output = {key: _iso(value) for key, value in row.items()}
    output.update({
        'status': status,
        'name': name,
        'kind': kind,
        'opened_at': _iso(opened_at),
    })
    return output


def visible_run_rows(
    rows: list[Mapping[str, Any]], *, is_operator: bool,
    excluded_legacy_ids: frozenset[int] = frozenset(),
    verified_metadata: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Keep legacy runs in server lists, suppress other unpublished runs.

    For nonoperators, unknown status is hidden (fail closed).  The required
    role check itself must still occur on the FastAPI route via auth middleware.
    """
    verified_metadata = verified_metadata or {}
    result = []
    for row in rows:
        run_id = int(row['run_id'])
        if run_id in excluded_legacy_ids:
            continue
        public = to_run_response(row, verified_metadata.get(run_id))
        if not is_operator and run_id != 1 and public['status'] not in {'검토 중', '확정', '참고'}:
            continue
        result.append(public)
    return result
