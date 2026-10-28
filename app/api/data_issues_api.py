from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer
from typing import Literal

from app.core import db
from app.core.auth import require_roles
from app.services.a05.duplicate_role_adapter import (
    attach_duplicate_roles,
    load_duplicate_roles,
)

router = APIRouter(
    prefix="/api/data-issues",
    tags=["A-05/A-06/A-08 통합 조회"]
)

operator = require_roles("operator")
swagger_bearer = HTTPBearer(auto_error=False)


@router.get("")
def list_data_issues(
    check_fn: Literal["A-05", "A-06", "A-08"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(operator),
    _swagger_auth = Depends(swagger_bearer),
):
    if check_fn is None:
        count_sql = """
            SELECT COUNT(*) AS cnt
            FROM data_issue
            WHERE check_fn IN ('A-05', 'A-06', 'A-08')
        """
        rows_sql = """
            SELECT issue_id, check_fn, error_code, check_name,
                   table_name, row_key, field_name, value_text,
                   reason, group_id, source_file, source_row_no,
                   upload_id, job_run_id, found_at,
                   review_status, resolution
            FROM data_issue
            WHERE check_fn IN ('A-05', 'A-06', 'A-08')
            ORDER BY issue_id DESC
            LIMIT %s OFFSET %s
        """
        count_params = ()
        rows_params = (limit, offset)
    else:
        count_sql = """
            SELECT COUNT(*) AS cnt
            FROM data_issue
            WHERE check_fn = %s
        """
        rows_sql = """
            SELECT issue_id, check_fn, error_code, check_name,
                   table_name, row_key, field_name, value_text,
                   reason, group_id, source_file, source_row_no,
                   upload_id, job_run_id, found_at,
                   review_status, resolution
            FROM data_issue
            WHERE check_fn = %s
            ORDER BY issue_id DESC
            LIMIT %s OFFSET %s
        """
        count_params = (check_fn,)
        rows_params = (check_fn, limit, offset)

    count_rows = db.read_only(count_sql, count_params)
    rows = db.read_only(rows_sql, rows_params)

    # A-05 중복 행에만 검증된 대표·사본 정보를 추가
    if any(
        row.get("check_fn") == "A-05"
        and row.get("error_code") == "A05_DUPLICATE_ROW"
        for row in rows
    ):
        roles = load_duplicate_roles()
        rows = attach_duplicate_roles(rows, roles)

    return {
        "total": int(count_rows[0]["cnt"]),
        "check_fn": check_fn,
        "limit": limit,
        "offset": offset,
        "items": rows,
        "source": "data_issue",
        "db_written": False,
    }

