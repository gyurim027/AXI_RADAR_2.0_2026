"""D-10 v2.3 / 77 priority_run read-only queries. Never modifies DB."""
from __future__ import annotations
from app.core import db

RUN_COLUMNS = "run_id, build_id, rule_version, created_at, note, period_start, period_end, admin_sampled_at, district_sampled_at"


def list_runs(limit: int = 50) -> list[dict]:
    return db.read_only(
        f"SELECT {RUN_COLUMNS} FROM priority_run ORDER BY created_at DESC, run_id DESC LIMIT %s",
        (limit,),
    )


def get_run(run_id: int) -> dict | None:
    rows = db.read_only(f"SELECT {RUN_COLUMNS} FROM priority_run WHERE run_id = %s", (run_id,))
    return rows[0] if rows else None


def candidate_counts(run_id: int) -> dict:
    """Information only: selected_yn is NOT an operational district decision."""
    rows = db.read_only(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(selected_yn = 'Y'), 0) AS selected, "
        "COALESCE(SUM(score IS NOT NULL), 0) AS scored "
        "FROM priority_candidate WHERE run_id = %s", (run_id,),
    )
    row = rows[0] if rows else {}
    return {"total": int(row.get("total") or 0), "selected": int(row.get("selected") or 0),
            "scored": int(row.get("scored") or 0)}
