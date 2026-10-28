"""운영 화면이 읽는 값 (I-05·I-06·I-03). 읽기만 하고, 알림만 71에 쓴다 (업무 알림 만들기 · 확인).

읽는 표: 85 job_run · 86 job_run_log · 71 alert_delivery · 84 data_upload · 70 access_audit (SQL v2.1)
알림(I-03): 71에 실패 말고 갱신 예정일·규정 개정·승인 결과 알림도 남긴다 (56·89·62를 보고 만듦, 10/28 SQL docs/ops/sql_71_alert_kind.sql)
대시보드(I-05, AD-01)에 더 읽는 표: 77 priority_run(최근 회차) · 62 setting_version(승인 현황) · 89 standard_change(규정 변경) (SQL v2.2)
                                · 56 source_list 갱신 주기·예정일 + 84 data_upload 확보 이력(자료 최신 여부) (SQL v2.3)
                                · 92 data_issue 미확인 검사 오류 · 62 산정 기준 카드 (SQL v2.3, 기능정의서 v0.5.4 AD-01 1-1·6-1)
"""
from __future__ import annotations

from app.core import db
from app.services.ops import alerts


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

    def running_same(self, run: dict) -> bool:
        """같은 기능·이름·연결 대상이 지금 '실행 중'인지 (다시 실행 두 번 막기, I-06)"""
        rows = db.read_only(
            "SELECT 1 AS x FROM job_run WHERE status = '실행 중' AND module <=> %s AND job_name = %s "
            "AND ref_table <=> %s AND ref_id <=> %s LIMIT 1",
            (run.get("module"), run.get("job_name"), run.get("ref_table"), run.get("ref_id")))
        return bool(rows)

    # ---------- 알림 (I-03, AD-00 종 아이콘) — 71 alert_delivery ----------
    # 실패 알림(job_run_id)과 업무 알림(alert_kind: staleData · regulation · approval, 10/28 SQL docs/ops/sql_71_alert_kind.sql).
    # 알림 종류 칸이 아직 없는 DB에서는 실패 알림만 읽는다 (옛 SQL로 다시 읽음).
    ALERT_COLS = "alert_delivery_id, job_run_id, alert_kind, ref_table, ref_id, message, sent_at, acknowledged_at, delivery_status"
    ALERT_WHERE = "(job_run_id IS NOT NULL OR alert_kind IS NOT NULL)"
    OLD_COLS = "alert_delivery_id, job_run_id, message, sent_at, acknowledged_at, delivery_status"
    APPROVAL_DAYS = 30                                    # 승인 결과는 최근 30일 것만 알림으로 만든다

    def list_alerts(self, unread_only: bool, limit: int) -> list[dict]:
        unread = " AND acknowledged_at IS NULL" if unread_only else ""
        order = " ORDER BY sent_at DESC, alert_delivery_id DESC LIMIT %s"
        try:
            return db.read_only(f"SELECT {self.ALERT_COLS} FROM alert_delivery WHERE {self.ALERT_WHERE}" + unread + order,
                                (limit,))
        except Exception:                                 # 알림 종류 칸 전 DB
            return db.read_only(f"SELECT {self.OLD_COLS} FROM alert_delivery WHERE job_run_id IS NOT NULL" + unread + order,
                                (limit,))

    def unread_alerts(self) -> int:
        try:
            rows = db.read_only(f"SELECT COUNT(*) AS n FROM alert_delivery WHERE {self.ALERT_WHERE} AND acknowledged_at IS NULL")
        except Exception:
            rows = db.read_only("SELECT COUNT(*) AS n FROM alert_delivery WHERE job_run_id IS NOT NULL "
                                "AND acknowledged_at IS NULL")
        return int(rows[0]["n"]) if rows else 0

    def acknowledge(self, alert_id: int, user_id: int) -> bool:
        """처음 확인한 사람·시각만 남긴다. 이미 확인한 알림은 바꾸지 않는다."""
        with db.connect() as con:
            with con.cursor() as cur:
                try:
                    cur.execute(f"SELECT 1 FROM alert_delivery WHERE alert_delivery_id = %s AND {self.ALERT_WHERE}", (alert_id,))
                except Exception:
                    cur.execute("SELECT 1 FROM alert_delivery WHERE alert_delivery_id = %s AND job_run_id IS NOT NULL",
                                (alert_id,))
                if not cur.fetchone():
                    return False
                cur.execute("UPDATE alert_delivery SET acknowledged_at = NOW(), acknowledged_by = %s, "
                            "delivery_status = '확인함' WHERE alert_delivery_id = %s AND acknowledged_at IS NULL",
                            (user_id, alert_id))
            con.commit()
        return True

    def alert_sources(self) -> tuple[list[dict], list[dict], list[dict]]:
        """알림 원인: 56 갱신 예정일 지난 자료 · 89 확인 안 한 규정 변경 · 62 최근 승인·반려"""
        c = ", ".join(["%s"] * len(self.CYCLES))
        stale = db.read_only(f"SELECT source_id, dataset, next_refresh_date FROM source_list "
                             f"WHERE refresh_cycle IN ({c}) AND next_refresh_date < CURDATE()", self.CYCLES)
        changes = db.read_only("SELECT standard_change_id, doc_name, where_text, change_type FROM standard_change "
                               "WHERE seen_at IS NULL")
        decided = db.read_only("SELECT setting_version_id, setting_kind, version_label, approval_status FROM setting_version "
                               "WHERE approval_status IN ('승인', '돌려보냄') AND approved_at >= NOW() - INTERVAL %s DAY",
                               (self.APPROVAL_DAYS,))
        return stale, changes, decided

    def save_alerts(self, want: list[dict]) -> None:
        """없는 알림만 새로 남기고(INSERT IGNORE + UNIQUE), 원인이 풀린 안 읽은 알림은 '해결됨'으로 닫는다."""
        with db.connect() as con:
            with con.cursor() as cur:
                for a in want:
                    cur.execute("INSERT IGNORE INTO alert_delivery (alert_kind, ref_table, ref_id, channel, recipient_ref, "
                                "sent_at, delivery_status, message) VALUES (%s, %s, %s, '화면', 'RADAR 운영자', NOW(), '보냄', %s)",
                                (a["kind"], a["ref_table"], a["ref_id"], a["message"]))
                for kind in alerts.CLOSE_WHEN_GONE:
                    active = [a["ref_id"] for a in want if a["kind"] == kind]
                    sql = ("UPDATE alert_delivery SET acknowledged_at = NOW(), delivery_status = '해결됨' "
                           "WHERE alert_kind = %s AND acknowledged_at IS NULL")
                    if active:
                        sql += " AND ref_id NOT IN (" + ", ".join(["%s"] * len(active)) + ")"
                    cur.execute(sql, (kind, *active))
            con.commit()

    def sync_alerts(self) -> None:
        """종 아이콘을 열 때마다 원인 표를 보고 알림을 맞춘다 (I-03). 알림 종류 칸 전 DB면 오류 → 부르는 쪽이 건너뜀."""
        stale, changes, decided = self.alert_sources()
        self.save_alerts(alerts.plan(stale, changes, decided))

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

    # 자료 최신 여부 (AD-01 2-1, SQL v2.3) — 규칙은 10/26 진이·규림 합의 + 은경
    CYCLES = ("월간", "분기", "반기", "연간")                       # 이 주기가 정해진 자료만 '빠짐'·'지남' 대상
    VALID = ("VALIDATION_PASSED", "VALIDATION_WARNING")           # 84 check_result 중 '확보'로 세는 값

    def data_freshness(self) -> dict:
        """56 자료마다: 지남(다음 갱신 예정일이 오늘보다 앞) · 빠짐(주기가 있는데 유효한 확보 이력이 없음) · 일정 미설정(주기 없음·수시)"""
        c, v = ", ".join(["%s"] * len(self.CYCLES)), ", ".join(["%s"] * len(self.VALID))
        rows = db.read_only(
            "SELECT "
            f" SUM(s.refresh_cycle IN ({c}) AND s.next_refresh_date < CURDATE()) AS stale,"
            f" SUM(s.refresh_cycle IN ({c}) AND NOT EXISTS (SELECT 1 FROM data_upload u WHERE u.source_id = s.source_id"
            f"     AND u.check_result IN ({v}))) AS missing,"
            f" SUM(s.refresh_cycle IS NULL OR s.refresh_cycle NOT IN ({c})) AS unscheduled,"
            " COUNT(*) AS total FROM source_list s",
            (*self.CYCLES, *self.CYCLES, *self.VALID, *self.CYCLES))
        r = rows[0] if rows else {}
        return {k: int(r.get(k) or 0) for k in ("stale", "missing", "unscheduled", "total")}

    # 검사 오류 (AD-01 1-1). 기능정의서 1-2: 형식·빈칸·중복은 고쳐서 다시 올리는 오류, 이상한 값(A-06)·같은 시설 의심(A-08)은
    # "고치지 않고 표시만 한다" → '다음에 할 일'은 고칠 수 있는 오류(A-05)만 세고, 나머지는 '확인 필요(참고)'로 따로 (10/27 세은 제안)
    FIX_FNS = ("A-05",)

    def checks_unreviewed(self) -> dict:
        """운영자가 아직 확인하지 않은 검사 결과 수 (SQL v2.3 92 data_issue, review_status NULL = 미확인).
        {"fix": 고쳐서 다시 올릴 오류(A-05), "reference": 표시만 하는 것(A-06·A-08 등), "total": 합}"""
        rows = db.read_only("SELECT check_fn, COUNT(*) AS n FROM data_issue WHERE review_status IS NULL GROUP BY check_fn")
        fix = sum(int(r["n"]) for r in rows if (r.get("check_fn") or "") in self.FIX_FNS)
        total = sum(int(r["n"]) for r in rows)
        return {"fix": fix, "reference": total - fix, "total": total}

    # 산정 기준 (AD-01 6-1, 기능정의서 v0.5.4): "승인 대기 버전이 있으면 그 버전을, 없으면 지금 쓰는 버전을 연다.
    # 지금 쓰는 버전은 시 도로과가 승인한 가장 최근 버전이다." — 62 setting_version 중 산정 설정 종류(I-02 설정 API와 같은 범위)
    from app.services.settings.repository import KINDS as CRITERIA_KINDS

    def criteria_card(self) -> dict | None:
        """승인 대기(제안) 중 가장 최근 것, 없으면 승인된 것 중 가장 최근 것. 둘 다 없으면 None."""
        k = ", ".join(["%s"] * len(self.CRITERIA_KINDS))
        cols = "setting_version_id, setting_kind, version_label, approval_status, proposed_at, approved_at"
        rows = db.read_only(f"SELECT {cols} FROM setting_version WHERE setting_kind IN ({k}) AND approval_status = '제안' "
                            "ORDER BY proposed_at DESC, setting_version_id DESC LIMIT 1", self.CRITERIA_KINDS)
        if not rows:
            rows = db.read_only(f"SELECT {cols} FROM setting_version WHERE setting_kind IN ({k}) "
                                "AND approval_status = '승인' ORDER BY approved_at DESC, setting_version_id DESC LIMIT 1",
                                self.CRITERIA_KINDS)
        return rows[0] if rows else None

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
