"""운영 화면이 읽는 값 (I-05·I-06·I-03). 읽기만 하고, 알림 확인만 71에 쓴다.

읽는 표: 85 job_run · 86 job_run_log · 71 alert_delivery · 84 data_upload · 70 access_audit (SQL v2.1)
대시보드(I-05, AD-01)에 더 읽는 표: 77 priority_run(최근 회차) · 62 setting_version(승인 현황) · 89 standard_change(규정 변경) (SQL v2.2)
"""
from __future__ import annotations

from app.core import db


class OpsRepository:
    def run_counts(self, days: int) -> dict:
        rows = db.read_only(
            "SELECT status, COUNT(*) AS n FROM job_run WHERE started_at >= NOW() - INTERVAL %s DAY GROUP BY status",
            (days,))
        return {r["status"]: int(r["n"]) for r in rows}

    def list_runs(self, days: int, status: str | None, kind: str | None, limit: int) -> list[dict]:
        sql = ("SELECT job_run_id, job_kind, job_name, module, ref_table, ref_id, status, started_at, finished_at, "
               "TIMESTAMPDIFF(MINUTE, started_at, COALESCE(finished_at, NOW())) AS minutes, row_cnt, error_code, cause "
               "FROM job_run WHERE started_at >= NOW() - INTERVAL %s DAY")
        args: list = [days]
        if status:
            sql += " AND status = %s"
            args.append(status)
        if kind:
            sql += " AND job_kind = %s"
            args.append(kind)
        sql += " ORDER BY started_at DESC, job_run_id DESC LIMIT %s"
        args.append(limit)
        return db.read_only(sql, args)

    def get_run(self, run_id: int) -> dict | None:
        rows = self.list_runs_by_id(run_id)
        if not rows:
            return None
        run = rows[0]
        run["logs"] = db.read_only(
            "SELECT logged_at, message FROM job_run_log WHERE job_run_id = %s ORDER BY logged_at, job_run_log_id",
            (run_id,))
        return run

    def list_runs_by_id(self, run_id: int) -> list[dict]:
        return db.read_only(
            "SELECT job_run_id, job_kind, job_name, module, ref_table, ref_id, status, started_at, finished_at, "
            "TIMESTAMPDIFF(MINUTE, started_at, COALESCE(finished_at, NOW())) AS minutes, row_cnt, error_code, cause "
            "FROM job_run WHERE job_run_id = %s", (run_id,))

    def list_alerts(self, unread_only: bool, limit: int) -> list[dict]:
        sql = ("SELECT alert_delivery_id, job_run_id, message, sent_at, acknowledged_at, delivery_status "
               "FROM alert_delivery WHERE job_run_id IS NOT NULL")
        if unread_only:
            sql += " AND acknowledged_at IS NULL"
        sql += " ORDER BY sent_at DESC, alert_delivery_id DESC LIMIT %s"
        return db.read_only(sql, (limit,))

    def unread_alerts(self) -> int:
        rows = db.read_only("SELECT COUNT(*) AS n FROM alert_delivery WHERE job_run_id IS NOT NULL "
                            "AND acknowledged_at IS NULL")
        return int(rows[0]["n"]) if rows else 0

    def acknowledge(self, alert_id: int, user_id: int) -> bool:
        """처음 확인한 사람·시각만 남긴다. 이미 확인한 알림은 바꾸지 않는다."""
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("SELECT 1 FROM alert_delivery WHERE alert_delivery_id = %s AND job_run_id IS NOT NULL",
                            (alert_id,))
                if not cur.fetchone():
                    return False
                cur.execute("UPDATE alert_delivery SET acknowledged_at = NOW(), acknowledged_by = %s, "
                            "delivery_status = '확인함' WHERE alert_delivery_id = %s AND acknowledged_at IS NULL",
                            (user_id, alert_id))
            con.commit()
        return True

    def upload_summary(self, days: int) -> dict:
        rows = db.read_only("SELECT COUNT(*) AS n, MAX(uploaded_at) AS last_at FROM data_upload "
                            "WHERE uploaded_at >= NOW() - INTERVAL %s DAY", (days,))
        r = rows[0] if rows else {"n": 0, "last_at": None}
        return {"count": int(r["n"] or 0), "last_at": r["last_at"]}

    # ---------- 대시보드 (I-05, 화면명세 AD-01) ----------
    RUN_BASE = "run_id, build_id, rule_version, created_at, note"
    RUN_V22 = ", period_start, period_end, admin_sampled_at, district_sampled_at"      # SQL v2.2에서 더한 칸

    def latest_run(self) -> dict | None:
        """가장 최근 회차(77). v2.1 DB면 v2.2 칸 없이 읽는다."""
        for cols in (self.RUN_BASE + self.RUN_V22, self.RUN_BASE):
            try:
                rows = db.read_only(f"SELECT {cols} FROM priority_run ORDER BY run_id DESC LIMIT 1")
                return rows[0] if rows else None
            except Exception:
                if cols == self.RUN_BASE:
                    raise
        return None

    def latest_calc(self) -> dict | None:
        """가장 최근 산정 실행(85, job_kind='산정')."""
        rows = db.read_only("SELECT job_run_id, status, ref_table, ref_id, started_at FROM job_run "
                            "WHERE job_kind = '산정' ORDER BY started_at DESC, job_run_id DESC LIMIT 1")
        return rows[0] if rows else None

    def approval_counts(self, year: int) -> dict:
        """올해 제안·승인·돌려보냄 수(62 approval_status). 제안은 제안 시각, 승인·돌려보냄은 처리 시각의 해로 센다."""
        rows = db.read_only(
            "SELECT approval_status AS st, COUNT(*) AS n FROM setting_version "
            "WHERE YEAR(CASE WHEN approval_status = '제안' THEN proposed_at ELSE approved_at END) = %s "
            "GROUP BY approval_status", (year,))
        return {r["st"]: int(r["n"]) for r in rows}

    def regulation_unseen(self) -> int:
        """운영자가 아직 확인하지 않은 규정 변경 수(89 seen_at 비어 있음)."""
        rows = db.read_only("SELECT COUNT(*) AS n FROM standard_change WHERE seen_at IS NULL")
        return int(rows[0]["n"]) if rows else 0

    def access_today(self) -> int:
        rows = db.read_only("SELECT COUNT(*) AS n FROM access_audit WHERE accessed_at >= CURDATE()")
        return int(rows[0]["n"]) if rows else 0


_repo: OpsRepository = OpsRepository()


def set_repository(repo: OpsRepository) -> None:
    global _repo
    _repo = repo


def get_repository() -> OpsRepository:
    return _repo
