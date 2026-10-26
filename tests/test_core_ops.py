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
from app.services.ops import repository as ops_repo


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
        self.assertEqual((j["run"], j["data"]["stale"], j["regulations"]), (None, None, 0))
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


if __name__ == "__main__":
    unittest.main()
