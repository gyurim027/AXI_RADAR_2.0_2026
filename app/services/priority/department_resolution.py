"""Read-only jurisdiction references and conservative candidate department output.

Official department decisions require a verified problem-to-jurisdiction mapping
and (when applicable) an F-02 road kind. Neither can be inferred from a score.
"""
from __future__ import annotations

from app.core import db
from app.services.priority.department_verified import resolve_verified_department

DISTRICTS = frozenset({"수정구", "중원구", "분당구"})


def unresolved_department(candidate: dict) -> dict:
    """Return the frontend contract without pretending an unverified assignment."""
    # Only trust an internal verified_problem object with traceable evidence.
    verified = candidate.get("verified_problem")
    if isinstance(verified, dict):
        return resolve_verified_department(
            gu=candidate.get("gu"), verified_problem=verified,
            read_reference=read_department_reference,
        )
    return {
        "department": None,
        "departmentStatus": "확인 필요",
        "departmentReason": "산정 지표와 담당 부서 문제 유형 간 확정 연결 및 F-02 도로 종류 입력이 없습니다.",
        "departmentInputs": {
            "gu": candidate.get("gu"),
            "jurisdictionId": None,
            "roadType": None,
        },
    }


def read_department_reference(jurisdiction_id: str, gu: str, read=None) -> dict:
    """Show traceable possible teams, never an automated assignment.

    Requires an explicit problem type ID selected from the reference table.
    Road classification and conditional routing must be confirmed separately.
    """
    if gu not in DISTRICTS:
        raise ValueError("invalid_gu")
    if not jurisdiction_id.startswith("JUR-") or len(jurisdiction_id) > 20:
        raise ValueError("invalid_jurisdiction_id")
    query = db.read_only if read is None else read
    problems = query(
        "SELECT jurisdiction_id, problem, mvp_scope, confirm_status, basis, note "
        "FROM jurisdiction WHERE jurisdiction_id = %s", (jurisdiction_id,)
    )
    if not problems:
        raise LookupError("unknown_jurisdiction_id")
    problem = problems[0]
    rows = query(
        "SELECT jurisdiction_dept_id, sort_no, gu_name, condition_text, dept_name, org_level "
        "FROM jurisdiction_dept WHERE jurisdiction_id = %s "
        "AND (gu_name = %s OR gu_name IS NULL) "
        "ORDER BY sort_no, jurisdiction_dept_id", (jurisdiction_id, gu)
    )
    options = [
        {
            "referenceId": row.get("jurisdiction_dept_id"),
            "name": row.get("dept_name"),
            "orgLevel": row.get("org_level"),
            "gu": row.get("gu_name"),
            "condition": row.get("condition_text"),
            "needsConditionCheck": bool(row.get("condition_text")),
        }
        for row in rows
    ]
    return {
        "jurisdictionId": problem["jurisdiction_id"],
        "problemType": problem["problem"],
        "gu": gu,
        "basisStatus": problem.get("confirm_status"),
        "mvpScope": problem.get("mvp_scope"),
        "department": None,
        "status": "확인 필요",
        "reason": "참조 후보 목록입니다. 확인된 문제 유형·F-02 도로 종류·조건 검증 없이 담당 부서를 확정하지 않습니다.",
        "options": options,
        "sourceTables": ["jurisdiction", "jurisdiction_dept"],
    }
