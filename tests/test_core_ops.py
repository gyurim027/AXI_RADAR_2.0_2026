"""실행 기록(I-06) · 실패 알림(I-03) · 운영 대시보드(I-05) 시험. 실제 DB 없이 돈다.
실행: uv run python -m pytest tests/test_core_ops.py
"""
import unittest
from datetime import date, datetime

from fastapi.testclient import TestClient

from app.core import job_run
from app.core.auth import make_token
from app.core.job_run import JobFailed, JobSkipped, track
from app.main import app
from app.services.ops import alerts, repository as ops_repo


class MemoryJobStore(job_run.JobStore):
    def __init__(self):
        self.runs, self.logs, self.alerts = {}, [], []

    def start(self, kind, name, module, ref_table, ref_id, triggered_by, request_id):
        rid = len(self.runs) + 1
        self.runs[rid] = dict(job_run_id=rid, job_kind=kind, job_name=name, module=module, ref_table=ref_table,
                              ref_id=ref_id, status="실행 중", started_at=datetime.now(), finished_at=None,
                              minutes=0, row_cnt=None, error_code=None, cause=None, triggered_by=triggered_by)
        return rid

    def log(self, run_id, message):
        self.logs.append(dict(job_run_id=run_id, logged_at=datetime.now(), message=message))

    def finish(self, run_id, status, row_cnt, error_code, cause, ref_table, ref_id):
        r = self.runs[run_id]
        r.update(status=status, row_cnt=row_cnt, error_code=error_code, cause=cause, finished_at=datetime.now())
        if ref_table:
            r.update(ref_table=ref_table, ref_id=ref_id)

    def alert_failure(self, run_id, message):
        self.alerts.append(dict(alert_delivery_id=len(self.alerts) + 1, job_run_id=run_id, message=message,
                                sent_at=datetime.now(), acknowledged_at=None, delivery_status="보냄", by=None))


class MemoryOpsRepo(ops_repo.OpsRepository):
    def __init__(self, store: MemoryJobStore):
        self.s = store

    def run_counts(self, days):
        out = {}
        for r in self.s.runs.values():
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out

    def list_runs(self, days, status, kind, limit):
        rows = [r for r in self.s.runs.values() if (not status or r["status"] == status) and (not kind or r["job_kind"] == kind)]
        return sorted(rows, key=lambda r: -r["job_run_id"])[:limit]

    def get_run(self, run_id):
        r = self.s.runs.get(run_id)
        return dict(r, logs=[l for l in self.s.logs if l["job_run_id"] == run_id]) if r else None

    def list_alerts(self, unread_only, limit):
        return [a for a in self.s.alerts if not unread_only or a["acknowledged_at"] is None][:limit]

    def unread_alerts(self):
        return sum(1 for a in self.s.alerts if a["acknowledged_at"] is None)

    def acknowledge(self, alert_id, user_id):
        for a in self.s.alerts:
            if a["alert_delivery_id"] == alert_id:
                if a["acknowledged_at"] is None:
                    a.update(acknowledged_at=datetime.now(), by=user_id, delivery_status="확인함")
                return True
        return False

    def upload_summary(self, days):
        return {"count": 7, "last_at": None}

    def access_today(self):
        return 3

    # 대시보드 (I-05 AD-01)
    run = None
    approvals = {}
    unseen = 0

    def latest_run(self):
        return self.run

    def latest_calc(self):
        rows = [r for r in self.s.runs.values() if r["job_kind"] == "산정"]
        return max(rows, key=lambda r: r["job_run_id"]) if rows else None

    def approval_counts(self, year):
        return self.approvals

    def regulation_unseen(self):
        return self.unseen

    freshness = {"stale": 0, "missing": 0, "unscheduled": 54, "total": 54}

    def data_freshness(self):
        return self.freshness

    checks = {"fix": 0, "reference": 0, "total": 0}
    criteria = None

    def checks_unreviewed(self):
        return self.checks

    def criteria_card(self):
        return self.criteria

    # 알림 원인 (56 갱신 예정일 지난 자료 · 89 확인 안 한 규정 변경 · 62 최근 승인·반려) — 시험마다 바꿈
    sources = ([], [], [])

    def alert_sources(self):
        return self.sources

    def save_alerts(self, want):
        """71 INSERT IGNORE(UNIQUE 종류·표·번호) + 원인이 풀린 안 읽은 알림 '해결됨' 닫기를 메모리로"""
        have = {(a.get("alert_kind"), a.get("ref_table"), a.get("ref_id")) for a in self.s.alerts}
        for w in want:
            if (w["kind"], w["ref_table"], w["ref_id"]) not in have:
                self.s.alerts.append(dict(alert_delivery_id=len(self.s.alerts) + 1, job_run_id=None, alert_kind=w["kind"],
                                          ref_table=w["ref_table"], ref_id=w["ref_id"], message=w["message"],
                                          sent_at=datetime.now(), acknowledged_at=None, delivery_status="보냄", by=None))
        for kind in alerts.CLOSE_WHEN_GONE:
            active = {w["ref_id"] for w in want if w["kind"] == kind}
            for a in self.s.alerts:
                if a.get("alert_kind") == kind and a["acknowledged_at"] is None and a["ref_id"] not in active:
                    a.update(acknowledged_at=datetime.now(), delivery_status="해결됨")

    def running_same(self, run):
        return any(r["status"] == "실행 중" and r["module"] == run.get("module") and r["job_name"] == run.get("job_name")
                   and r["ref_id"] == run.get("ref_id") for r in self.s.runs.values())


def _bearer(role):
    tok, _ = make_token({"user_id": 9, "login_id": role, "role": role, "gu": None})
    return {"Authorization": "Bearer " + tok}


class JobRunTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryJobStore()
        job_run.set_store(self.store)

    def tearDown(self):
        job_run.set_store(job_run.JobStore())

    def test_success_with_logs_and_rows(self):
        with track("좌표", "2026 하반기 민원 좌표", module="AI-03") as job:
            job.log("주소 2,546건을 읽었습니다")
            job.rows(2546)
        r = self.store.runs[1]
        self.assertEqual((r["status"], r["row_cnt"], r["module"]), ("성공", 2546, "AI-03"))
        self.assertEqual(self.store.logs[0]["message"], "주소 2,546건을 읽었습니다")
        self.assertEqual(self.store.alerts, [])

    def test_warning(self):
        with track("좌표", "좌표") as job:
            job.warn("주소 423건은 좌표를 못 붙였습니다")
        self.assertEqual(self.store.runs[1]["status"], "경고")

    def test_job_failed_keeps_cause_and_alerts(self):
        with self.assertRaises(JobFailed):
            with track("산정", "2028 연간 산정", module="ENGINE"):
                raise JobFailed("missing_column", "보도 면적 열이 비어 있음")
        r = self.store.runs[1]
        self.assertEqual((r["status"], r["error_code"], r["cause"]), ("실패", "missing_column", "보도 면적 열이 비어 있음"))
        self.assertIn("2028 연간 산정 실행이 실패했습니다", self.store.alerts[0]["message"])

    def test_other_error_hides_text(self):
        with self.assertRaises(ValueError):
            with track("분류", "민원 분류"):
                raise ValueError("민원 원문 홍길동 010-1234-5678")
        r = self.store.runs[1]
        self.assertEqual(r["cause"], "처리 중 오류(ValueError)")
        self.assertNotIn("010", self.store.alerts[0]["message"])

    def test_skipped(self):
        with track("수집", "공공데이터 반기 수집"):
            raise JobSkipped("새 파일 없음")
        self.assertEqual(self.store.runs[1]["status"], "건너뜀")

    def test_store_down_does_not_block_work(self):
        class Broken(job_run.JobStore):
            def start(self, *a):
                raise ConnectionError("db down")
        job_run.set_store(Broken())
        done = []
        with track("검사", "형식 검사") as job:
            job.log("x")
            done.append(1)
        self.assertEqual(done, [1])

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            with track("아무거나", "x"):
                pass

    def test_aggregate_kind(self):
        """격자 집계·재계산(B-02 등)은 '산정'이 아니라 '집계'로 남긴다 (10/27). 대시보드 '최근 산정'에 섞이지 않게"""
        with track("집계", "격자 EXT_ 열 다시 채우기", module="B-02"):
            pass
        self.assertEqual(self.store.runs[1]["job_kind"], "집계")

    def test_system_exit_is_failure_not_running(self):
        """명령이 SystemExit로 멈춰도 '실행 중'으로 남지 않는다 (남으면 다시 실행이 '이미 도는 중'으로 막힘)"""
        with self.assertRaises(SystemExit):
            with track("검사", "업무분장 변경 확인"):
                raise SystemExit("읽을 수 없는 파일 형식: .doc (.hwp · .hwpx · .pdf · .txt)")
        r = self.store.runs[1]
        self.assertEqual((r["status"], r["error_code"]), ("실패", "SystemExit"))
        self.assertIn("읽을 수 없는 파일 형식", r["cause"])
        self.assertEqual(len(self.store.alerts), 1)
        with self.assertRaises(SystemExit):
            with track("검사", "정상 종료"):
                raise SystemExit(0)
        self.assertEqual(self.store.runs[2]["status"], "성공")


class OpsApiTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryJobStore()
        job_run.set_store(self.store)
        ops_repo.set_repository(MemoryOpsRepo(self.store))
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")
        with track("업로드", "민원 파일 올리기"):
            pass
        try:
            with track("산정", "2028 연간 산정") as job:
                job.log("산정을 시작했습니다")
                raise JobFailed("missing_column", "보도 면적 열이 비어 있음")
        except JobFailed:
            pass

    def tearDown(self):
        job_run.set_store(job_run.JobStore())
        ops_repo.set_repository(ops_repo.OpsRepository())

    def test_operator_only(self):
        self.assertEqual(self.c.get("/api/ops/dashboard").status_code, 401)
        self.assertEqual(self.c.get("/api/ops/dashboard", headers=_bearer("city")).status_code, 403)

    def test_dashboard(self):
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual((j["runs"]["success"], j["runs"]["failure"], j["alerts"]["unread"]), (1, 1, 1))
        self.assertEqual(j["uploads"]["count"], 7)
        self.assertEqual(j["next"]["key"], "failed")                       # 가장 최근 산정이 실패 → 다시 실행 안내
        self.assertEqual((j["run"], j["data"]["stale"], j["regulations"]), (None, 0, 0))
        self.assertEqual(j["approvals"], {"pending": 0, "approved": 0, "returned": 0})

    def test_dashboard_approvals_regulations_run(self):
        repo = ops_repo.get_repository()
        repo.run = {"run_id": 3, "created_at": datetime(2027, 1, 5, 9, 0), "period_start": date(2026, 1, 1),
                    "period_end": date(2026, 12, 31), "admin_sampled_at": None}
        repo.approvals = {"제안": 2, "승인": 5, "돌려보냄": 1}
        repo.unseen = 4
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual(j["approvals"], {"pending": 2, "approved": 5, "returned": 1})
        self.assertEqual(j["regulations"], 4)
        self.assertEqual((j["run"]["id"], j["run"]["periodStart"], j["run"]["status"]), (3, "2026.01.01", None))
        self.assertTrue(any("회차 상태" in n for n in j["notes"]))

    def test_dashboard_data_freshness(self):
        repo = ops_repo.get_repository()
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual(j["data"], {"stale": 0, "missing": 0, "unscheduled": 54, "total": 54})   # 주기 없는 자료는 '빠짐'이 아님
        repo.freshness = {"stale": 1, "missing": 3, "unscheduled": 50, "total": 54}
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual((j["next"]["key"], j["next"]["text"]), ("missing", "빠진 자료 3종을 올려 주세요."))   # 빠진 자료가 먼저

        def old_db():
            raise RuntimeError("Unknown column refresh_cycle")
        repo.data_freshness = old_db
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertIsNone(j["data"]["missing"])
        self.assertTrue(any("SQL v2.3" in n for n in j["notes"]))

    def test_dashboard_check_errors(self):
        """v0.5.4 AD-01 1-1 다음에 할 일: 빠진 자료 → 검사 오류(92 미확인) → … → 실행 실패"""
        repo = ops_repo.get_repository()
        repo.checks = {"fix": 1301, "reference": 3147, "total": 4448}
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual(j["checks"], {"fix": 1301, "reference": 3147, "unreviewed": 4448})
        self.assertEqual((j["next"]["key"], j["next"]["text"], j["next"]["to"]),
                         ("checks", "검사에서 걸린 자료 1301건을 고쳐 주세요.", "/admin/data/checks"))   # 고칠 수 있는 것(A-05)만, 산정 실패보다 먼저
        repo.checks = {"fix": 0, "reference": 3147, "total": 3147}         # 표시만 하는 것(A-06·A-08)만 남으면 다음 할 일을 막지 않음
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual((j["checks"]["reference"], j["next"]["key"]), (3147, "failed"))
        repo.checks = {"fix": 1301, "reference": 3147, "total": 4448}
        repo.freshness = {"stale": 0, "missing": 2, "unscheduled": 52, "total": 54}
        self.assertEqual(self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()["next"]["key"], "missing")
        repo.freshness, repo.checks = {"stale": 0, "missing": 0, "unscheduled": 54, "total": 54}, {"fix": 0, "reference": 0, "total": 0}
        self.assertEqual(self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()["next"]["key"], "failed")

        def old_db():
            raise RuntimeError("Table 'data_issue' doesn't exist")
        repo.checks_unreviewed = old_db
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertEqual((j["checks"]["unreviewed"], j["next"]["key"]), (None, "failed"))
        self.assertTrue(any("92 data_issue" in n for n in j["notes"]))

    def test_dashboard_criteria_card(self):
        """v0.5.4 AD-01 6-1: 승인 대기 버전이 있으면 그 버전, 없으면 지금 쓰는 버전(승인된 가장 최근)"""
        repo = ops_repo.get_repository()
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertIsNone(j["criteria"])
        repo.criteria = {"setting_version_id": 12, "setting_kind": "가중치", "version_label": "가중치 v3",
                         "approval_status": "제안", "proposed_at": datetime(2026, 10, 20, 9, 0), "approved_at": None}
        c = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()["criteria"]
        self.assertEqual((c["id"], c["pending"], c["status"], c["at"], c["to"]),
                         (12, True, "승인 대기", "2026.10.20", "/admin/standards/criteria/12"))
        repo.criteria = dict(repo.criteria, approval_status="승인", approved_at=datetime(2026, 10, 22, 15, 0))
        c = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()["criteria"]
        self.assertEqual((c["pending"], c["status"], c["at"], c["label"]), (False, "사용 중", "2026.10.22", "가중치 v3"))

    def test_dashboard_survives_missing_table(self):
        repo = ops_repo.get_repository()

        def boom(*a):
            raise RuntimeError("no table")
        repo.regulation_unseen = boom
        j = self.c.get("/api/ops/dashboard", headers=_bearer("operator")).json()
        self.assertIsNone(j["regulations"])
        self.assertIn("89 standard_change를 읽지 못함", j["notes"])

    def test_runs_filter_and_detail(self):
        h = _bearer("operator")
        rows = self.c.get("/api/ops/runs?status=실패", headers=h).json()["runs"]
        self.assertEqual([r["name"] for r in rows], ["2028 연간 산정"])
        self.assertEqual(rows[0]["cause"], "보도 면적 열이 비어 있음")
        d = self.c.get(f"/api/ops/runs/{rows[0]['id']}", headers=h).json()
        self.assertTrue(d["logs"][0].endswith("산정을 시작했습니다"))
        self.assertEqual(self.c.get("/api/ops/runs?status=이상함", headers=h).status_code, 400)
        self.assertEqual(self.c.get("/api/ops/runs/999", headers=h).status_code, 404)

    def test_business_alerts(self):
        """실패 말고 갱신 예정일·규정 개정·승인 결과 알림 (I-03, 10/28). 읽음은 71에 남고, 원인이 풀리면 '해결됨'으로 닫힘"""
        h = _bearer("operator")
        repo = ops_repo.get_repository()
        repo.sources = ([{"source_id": "DAT-06", "dataset": "주정차 위반 단속 위치", "next_refresh_date": date(2026, 7, 1)}],
                        [{"standard_change_id": 5, "doc_name": "도로교통법", "where_text": "제32조", "change_type": "바뀜"}],
                        [{"setting_version_id": 9, "setting_kind": "담당 부서 표", "version_label": "x", "approval_status": "돌려보냄"}])
        n = self.c.get("/api/ops/notifications", headers=h).json()["notifications"]
        by = {x["kind"]: x for x in n}
        self.assertEqual(sorted(by), ["approval", "failure", "regulation", "staleData"])
        self.assertIn("갱신 예정일(2026.07.01)이 지났습니다", by["staleData"]["text"])
        self.assertEqual((by["regulation"]["refTable"], by["regulation"]["refId"]), ("standard_change", "5"))
        self.assertEqual(by["approval"]["text"], "담당 부서 표 수정안 제안이 반려되었습니다. 사유를 확인해 주세요.")
        self.assertEqual(self.c.get("/api/ops/dashboard", headers=h).json()["alerts"]["unread"], 4)
        self.assertEqual(self.c.post(f"/api/ops/notifications/{by['approval']['id']}/read", headers=h).status_code, 200)
        again = self.c.get("/api/ops/notifications", headers=h).json()["notifications"]
        self.assertEqual(len(again), 4)                                    # 다시 열어도 같은 알림이 또 생기지 않음
        self.assertTrue({x["kind"]: x for x in again}["approval"]["read"])  # 읽음이 남아 있음
        repo.sources = ([], [], repo.sources[2])                            # 자료를 다시 올림 · 규정 변경을 확인함
        left = self.c.get("/api/ops/notifications?unread=true", headers=h).json()["notifications"]
        self.assertEqual([x["kind"] for x in left], ["failure"])
        closed = {x["kind"]: x for x in self.c.get("/api/ops/notifications", headers=h).json()["notifications"]}
        self.assertEqual(closed["staleData"]["status"], "해결됨")

    def test_alert_plan_text(self):
        p = alerts.plan([], [], [{"setting_version_id": 3, "setting_kind": "가중치", "version_label": "v2",
                                  "approval_status": "승인"}])
        self.assertEqual(p[0]["message"], "가중치 v2 제안이 승인되었습니다. 다음 산정부터 사용할 수 있습니다.")
        self.assertEqual((p[0]["kind"], p[0]["ref_table"], p[0]["ref_id"]), ("approval", "setting_version", "3"))

    def test_notifications_read(self):
        h = _bearer("operator")
        n = self.c.get("/api/ops/notifications?unread=true", headers=h).json()["notifications"]
        self.assertEqual((len(n), n[0]["kind"], n[0]["read"]), (1, "failure", False))
        self.assertEqual(self.c.post(f"/api/ops/notifications/{n[0]['id']}/read", headers=h).status_code, 200)
        self.assertEqual(self.c.get("/api/ops/notifications?unread=true", headers=h).json()["notifications"], [])
        self.assertEqual(self.c.post("/api/ops/notifications/999/read", headers=h).status_code, 404)


class RerunApiTests(unittest.TestCase):
    """I-06 다시 실행 (AD-07 1-2): 실패한 실행만, 등록한 기능만, 처음부터, 누른 사람·원래 번호를 남김"""

    def setUp(self):
        from app.core import rerun
        self.rerun = rerun
        rerun.ASYNC = False
        self.store = MemoryJobStore()
        job_run.set_store(self.store)
        ops_repo.set_repository(MemoryOpsRepo(self.store))
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")
        self.calls = []
        self.fail_again = False

        def again(ref_table, ref_id, user_id):              # 시험용 기능: 같은 일을 처음부터 (안에서 track)
            self.calls.append((ref_table, ref_id, user_id))
            with track("산정", "2028 연간 산정", module="TEST-ENGINE", ref_table=ref_table, ref_id=ref_id) as job:
                if self.fail_again:
                    raise JobFailed("missing_column", "보도 면적 열이 비어 있음")
                job.rows(10)
        rerun.register_rerun("TEST-ENGINE", again)
        for module in ("TEST-ENGINE", "AI-03"):               # AI-03은 등록 안 한 기능
            try:
                with track("산정" if module == "TEST-ENGINE" else "좌표", "2028 연간 산정" if module == "TEST-ENGINE" else "AI-03 좌표",
                           module=module, ref_table="priority_run", ref_id=7):
                    raise JobFailed("missing_column", "보도 면적 열이 비어 있음")
            except JobFailed:
                pass
        with track("업로드", "민원 파일 올리기", module="C-09"):
            pass

    def tearDown(self):
        self.rerun.ASYNC = True
        self.rerun._REG.pop("TEST-ENGINE", None)
        job_run.set_store(job_run.JobStore())
        ops_repo.set_repository(ops_repo.OpsRepository())

    def _id(self, module):
        return next(r["job_run_id"] for r in self.store.runs.values() if r["module"] == module)

    def test_can_rerun_flag(self):
        rows = {r["module"]: r["canRerun"] for r in self.c.get("/api/ops/runs", headers=_bearer("operator")).json()["runs"]}
        self.assertEqual(rows, {"TEST-ENGINE": True, "AI-03": False, "C-09": False})

    def test_rerun_from_start(self):
        old = self._id("TEST-ENGINE")
        r = self.c.post(f"/api/ops/runs/{old}/rerun", headers=_bearer("operator"))
        self.assertEqual((r.status_code, r.json()["rerunOf"]), (202, old))
        self.assertEqual(self.calls, [("priority_run", "7", 9)])
        new = max(self.store.runs.values(), key=lambda x: x["job_run_id"])
        self.assertEqual((new["status"], new["triggered_by"], new["row_cnt"]), ("성공", 9, 10))
        first = [l["message"] for l in self.store.logs if l["job_run_id"] == new["job_run_id"]][0]
        self.assertEqual(first, f"실행 #{old}(실패)을 처음부터 다시 실행")
        self.assertEqual(self.store.runs[old]["status"], "실패")                # 원래 기록은 그대로

    def test_rerun_fails_again_is_recorded(self):
        self.fail_again = True
        before = len(self.store.alerts)
        self.assertEqual(self.c.post(f"/api/ops/runs/{self._id('TEST-ENGINE')}/rerun", headers=_bearer("operator")).status_code, 202)
        new = max(self.store.runs.values(), key=lambda x: x["job_run_id"])
        self.assertEqual(new["status"], "실패")
        self.assertEqual(len(self.store.alerts), before + 1)                    # 다시 실패하면 알림도 다시

    def test_refusals(self):
        h = _bearer("operator")
        ok_id = self._id("C-09")
        self.assertEqual(self.c.post(f"/api/ops/runs/{ok_id}/rerun", headers=h).json()["error"]["code"], "not_failed")
        self.assertEqual(self.c.post(f"/api/ops/runs/{self._id('AI-03')}/rerun", headers=h).json()["error"]["code"],
                         "rerun_not_supported")
        self.assertEqual(self.c.post("/api/ops/runs/999/rerun", headers=h).status_code, 404)
        self.assertEqual(self.c.post(f"/api/ops/runs/{self._id('TEST-ENGINE')}/rerun", headers=_bearer("city")).status_code, 403)
        self.store.start("산정", "2028 연간 산정", "TEST-ENGINE", "priority_run", "7", None, None)   # 같은 것이 실행 중
        r = self.c.post(f"/api/ops/runs/{self._id('TEST-ENGINE')}/rerun", headers=h)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "already_running"))
        self.assertEqual(self.calls, [])


class StandardsRerunTests(unittest.TestCase):
    """A-11 법령 개정 확인 · A-12 업무분장 변경 확인의 '다시 실행' (I-06, app/services/standards/rerun_hooks.py)"""

    def setUp(self):
        import sys
        import types
        from app.core import rerun
        from app.services.standards import rerun_hooks
        self.rerun, self.hooks, self.sys = rerun, rerun_hooks, sys
        rerun.ASYNC = False
        self.store = MemoryJobStore()
        job_run.set_store(self.store)
        ops_repo.set_repository(MemoryOpsRepo(self.store))
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")
        self.seen, self.fail = [], True

        def fake_main(argv):                                   # A-12 명령 대신 (실제 문서 없이): 입력만 받고 성공/실패
            with track("검사", "업무분장 변경 확인 (시험)", module="A-12") as job:
                rerun_hooks.remember(job, "A-12", argv)
                self.seen.append(list(argv))
                if self.fail:
                    raise JobFailed("read_failed", "새 판 파일을 읽지 못함")
                job.rows(3)
        mod = types.ModuleType("tests_fake_a12")
        mod.main = fake_main
        sys.modules["tests_fake_a12"] = mod
        self.old_script = rerun_hooks.SCRIPTS["A-12"]
        rerun_hooks.SCRIPTS["A-12"] = "tests_fake_a12"

    def tearDown(self):
        self.hooks.SCRIPTS["A-12"] = self.old_script
        self.sys.modules.pop("tests_fake_a12", None)
        self.rerun.ASYNC = True
        job_run.set_store(job_run.JobStore())
        ops_repo.set_repository(ops_repo.OpsRepository())

    def _latest(self):
        return max(self.store.runs.values(), key=lambda x: x["job_run_id"])

    def test_registered_on_server_start(self):
        self.assertTrue(self.rerun.can_rerun("A-11") and self.rerun.can_rerun("A-12"))

    def test_paths_become_absolute(self):
        from pathlib import Path
        out = self.hooks.absolute(["--old", "data/old", "--name", "업무분장", "--new=data/new"], ("--old", "--new"))
        self.assertEqual(out[0:2], ["--old", str(Path("data/old").resolve())])
        self.assertEqual(out[2:4], ["--name", "업무분장"])
        self.assertEqual(out[4], f"--new={Path('data/new').resolve()}")

    def test_rerun_with_same_input(self):
        from pathlib import Path
        with self.assertRaises(JobFailed):
            self.sys.modules["tests_fake_a12"].main(["--old", "old_dir", "--new", "new_dir", "--no-ai"])
        old = self._latest()["job_run_id"]
        h = _bearer("operator")
        self.assertTrue(self.c.get(f"/api/ops/runs/{old}", headers=h).json()["canRerun"])
        self.fail = False
        r = self.c.post(f"/api/ops/runs/{old}/rerun", headers=h)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(self.seen[-1], ["--old", str(Path("old_dir").resolve()), "--new", str(Path("new_dir").resolve()), "--no-ai"])
        new = self._latest()
        self.assertEqual((new["status"], new["triggered_by"], new["module"]), ("성공", 9, "A-12"))
        logs = [l["message"] for l in self.store.logs if l["job_run_id"] == new["job_run_id"]]
        self.assertEqual(logs[0], f"실행 #{old}(실패)을 처음부터 다시 실행")
        self.assertTrue(logs[1].startswith(self.hooks.PREFIX))              # 다시 실행한 것도 또 다시 실행 가능

    def test_old_run_without_input_is_refused(self):
        try:
            with track("검사", "업무분장 변경 확인 (옛 실행)", module="A-12"):
                raise JobFailed("read_failed", "x")
        except JobFailed:
            pass
        old = self._latest()["job_run_id"]
        h = _bearer("operator")
        self.assertFalse(self.c.get(f"/api/ops/runs/{old}", headers=h).json()["canRerun"])
        r = self.c.post(f"/api/ops/runs/{old}/rerun", headers=h)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "rerun_input_missing"))
        self.assertEqual(self.seen, [])

    def test_a11_command_logs_input_and_fails_cleanly(self):
        """실제 A-11 명령: 없는 새 조각 파일 → 실패로 남고, 다시 실행용 입력(절대 경로)이 로그에 있다"""
        from pathlib import Path
        from scripts import standards_check_law_revision as a11
        with self.assertRaises(FileNotFoundError):
            a11.main(["--new-chunks", "out/없는_조각.jsonl", "--no-save"])
        run = self._latest()
        self.assertEqual((run["module"], run["status"]), ("A-11", "실패"))
        logs = [l for l in self.store.logs if l["job_run_id"] == run["job_run_id"]]
        self.assertEqual(self.hooks.saved_argv({"logs": logs}),
                         ["--new-chunks", str(Path("out/없는_조각.jsonl").resolve()), "--no-save"])


if __name__ == "__main__":
    unittest.main()
