"""C-09 API 시험: 로그인(operator만) · 실행 기록 · 실패 알림 · 올린 기록. DB는 가짜로 바꿔 끼움."""
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import c09_upload_api as api
from app.core import job_run
from app.core.auth import make_token
from app.core.responses import CamelCaseMiddleware, install_error_handlers
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import GRID, SOURCE, general, spp, xlsx

QS = dict(source=SOURCE, refDate="2025-11-30", periodStart="2025-11-01", periodEnd="2025-11-30",
          fileName="민원 상세정보 현황-20261022190720.xlsx")
OPERATOR_ID = 9


def bearer(role="operator", user_id=OPERATOR_ID):
    tok, _ = make_token({"user_id": user_id, "login_id": role, "role": role, "gu": None})
    return {"Authorization": "Bearer " + tok}


class MemoryJobStore(job_run.JobStore):
    """실행 기록(85·86)과 실패 알림(71)을 메모리에 쌓는 시험용 저장소."""

    def __init__(self):
        self.runs, self.logs, self.alerts = {}, [], []

    def start(self, kind, name, module, ref_table, ref_id, triggered_by, request_id):
        rid = len(self.runs) + 1
        self.runs[rid] = dict(kind=kind, name=name, module=module, status="실행 중", triggered_by=triggered_by,
                              request_id=request_id, row_cnt=None, error_code=None, cause=None, ref_table=ref_table, ref_id=ref_id)
        return rid

    def log(self, run_id, message):
        self.logs.append((run_id, message))

    def finish(self, run_id, status, row_cnt, error_code, cause, ref_table, ref_id):
        self.runs[run_id].update(status=status, row_cnt=row_cnt, error_code=error_code, cause=cause)
        if ref_table:
            self.runs[run_id].update(ref_table=ref_table, ref_id=ref_id)

    def alert_failure(self, run_id, message):
        self.alerts.append((run_id, message))


def make_app():
    app = FastAPI()
    app.add_middleware(CamelCaseMiddleware)
    install_error_handlers(app)
    app.include_router(api.router)
    return app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(GRID)
        self.jobs = MemoryJobStore()
        job_run.set_store(self.jobs)
        self.patches = [
            mock.patch.object(api.db, "is_configured", return_value=True),
            mock.patch.object(api.db, "raw_connection", return_value=mock.Mock()),
            mock.patch.object(api, "MySQLStore", side_effect=lambda con: self.store),
        ]
        for p in self.patches:
            p.start()
        self.c = TestClient(make_app())
        self.data = xlsx([spp(1), general(2)])

    def tearDown(self):
        for p in self.patches:
            p.stop()
        job_run.set_store(job_run.JobStore())

    def post(self, data=None, headers=None, **over):
        return self.c.post("/api/c09/uploads", params={**QS, **over}, content=self.data if data is None else data,
                           headers=bearer() if headers is None else headers)

    # --- 올리기 ---
    def test_upload_ok_records_who_and_job_run(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.text)
        j = r.json()
        self.assertEqual((j["uploadId"], j["rows"], j["new"], j["checkResult"]), (1, 2, 2, "통과"))
        up = self.store.uploads[1]
        self.assertEqual(up["file_name"], "민원 상세정보 현황-20261022190720.xlsx")
        self.assertEqual(up["uploaded_by"], OPERATOR_ID)                    # 올린 운영자 계정이 자동으로 기록됨
        run = self.jobs.runs[1]
        self.assertEqual((run["kind"], run["module"], run["status"], run["triggered_by"]), ("업로드", "C-09", "성공", OPERATOR_ID))
        self.assertEqual((run["ref_table"], run["ref_id"], run["row_cnt"]), ("data_upload", "1", 2))
        self.assertEqual(self.jobs.alerts, [])

    def test_second_upload_is_existing(self):
        self.post()
        j = self.post().json()
        self.assertEqual((j["new"], j["existing"], j["updated"]), (0, 2, 0))

    # --- 로그인 · 역할 ---
    def test_login_required(self):
        r = self.post(headers={})
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (401, "login_required"))
        self.assertEqual(self.store.uploads, {})

    def test_only_operator(self):
        for role in ("city", "district"):
            r = self.post(headers=bearer(role))
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (403, "forbidden_role"), role)
        self.assertEqual(self.store.uploads, {})

    # --- 입력 값 오류: 기록도 알림도 남기지 않음 ---
    def test_source_and_period_are_required(self):
        params = {k: v for k, v in QS.items() if k != "source"}
        r = self.c.post("/api/c09/uploads", params=params, content=self.data, headers=bearer())
        self.assertEqual(r.status_code, 422)
        r = self.post(periodEnd="2025-11-15")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "invalid_period"))
        self.assertEqual((self.store.uploads, self.jobs.runs, self.jobs.alerts), ({}, {}, []))

    def test_empty_body(self):
        self.assertEqual(self.post(data=b"").status_code, 400)

    # --- 파일 오류: 84에 실패 한 줄 + 실행 기록 실패 + 운영자 알림 ---
    def test_bad_file_leaves_failed_run_and_alert(self):
        r = self.post(data=b"a,b\n1,2\n")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "unreadable_file"))
        self.assertTrue(self.store.uploads[1]["check_result"].startswith("실패"))
        self.assertEqual(self.jobs.runs[1]["status"], "실패")
        self.assertEqual(self.jobs.runs[1]["error_code"], "unreadable_file")
        self.assertEqual(len(self.jobs.alerts), 1)
        self.assertIn("엑셀", self.jobs.alerts[0][1])

    def test_period_mismatch_is_422_without_raw_text(self):
        r = self.post(data=xlsx([general(1, received="2025-12-03", title="원문ZQX")]))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "period_mismatch"))
        everything = r.text + repr(self.jobs.runs) + repr(self.jobs.logs) + repr(self.jobs.alerts) + repr(self.store.uploads)
        self.assertNotIn("ZQX", everything)

    def test_job_run_failure_does_not_block_the_load(self):
        class Broken(job_run.JobStore):
            def start(self, *a, **k):
                raise RuntimeError("85 표 없음")                            # v2 DB: 85·86 표가 아직 없는 경우
        job_run.set_store(Broken())
        r = self.post()
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(len(self.store.complaints), 2)

    def test_db_not_configured(self):
        with mock.patch.object(api.db, "is_configured", return_value=False):
            self.assertEqual(self.post().status_code, 503)

    # --- 올린 기록 ---
    def test_list_uploads(self):
        self.post()
        self.post(periodStart="2025-11-01")
        r = self.c.get("/api/c09/uploads", params={"limit": 1}, headers=bearer())
        self.assertEqual(r.status_code, 200)
        rows = r.json()["uploads"]
        self.assertEqual([u["uploadId"] for u in rows], [2])
        self.assertEqual(rows[0]["checkResult"], "통과")
        self.assertIn("dataName", rows[0])

    def test_list_requires_operator(self):
        self.assertEqual(self.c.get("/api/c09/uploads").status_code, 401)
        self.assertEqual(self.c.get("/api/c09/uploads", headers=bearer("city")).status_code, 403)
