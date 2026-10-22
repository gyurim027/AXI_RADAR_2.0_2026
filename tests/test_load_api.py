"""C-09 API 시험 (DB는 가짜로 바꿔 끼움)."""
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import c09_upload_api as api
from app.core.responses import CamelCaseMiddleware, install_error_handlers
from app.services.load.pipeline import run_load
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import GRID, SOURCE, general, spp, xlsx

QS = dict(source=SOURCE, refDate="2025-11-30", periodStart="2025-11-01", periodEnd="2025-11-30",
          fileName="민원 상세정보 현황-20261022190720.xlsx")


def make_app():
    app = FastAPI()
    app.add_middleware(CamelCaseMiddleware)
    install_error_handlers(app)
    app.include_router(api.router)
    return app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(GRID)
        self.patches = [
            mock.patch.object(api.db, "is_configured", return_value=True),
            mock.patch.object(api, "_load_sync", side_effect=lambda data, name, meta: run_load(data, name, meta, self.store)),
        ]
        for p in self.patches:
            p.start()
        self.c = TestClient(make_app())
        self.data = xlsx([spp(1), general(2)])

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def post(self, data=None, **over):
        return self.c.post("/api/c09/uploads", params={**QS, **over}, content=self.data if data is None else data)

    def test_upload_ok(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.text)
        j = r.json()
        self.assertEqual((j["uploadId"], j["rows"], j["new"], j["checkResult"]), (1, 2, 2, "통과"))
        self.assertEqual(self.store.uploads[1]["file_name"], "민원 상세정보 현황-20261022190720.xlsx")

    def test_second_upload_is_existing(self):
        self.post()
        j = self.post().json()
        self.assertEqual((j["new"], j["existing"], j["updated"]), (0, 2, 0))

    def test_source_and_period_are_required(self):
        params = {k: v for k, v in QS.items() if k != "source"}
        r = self.c.post("/api/c09/uploads", params=params, content=self.data)
        self.assertEqual(r.status_code, 422)
        r = self.post(periodEnd="2025-11-15")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "invalid_period"))

    def test_bad_file(self):
        r = self.post(data=b"a,b\n1,2\n")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "unreadable_file"))
        r = self.post(data=b"")
        self.assertEqual(r.status_code, 400)

    def test_period_mismatch_is_422_without_raw_text(self):
        r = self.post(data=xlsx([general(1, received="2025-12-03", title="원문ZQX")]))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "period_mismatch"))
        self.assertNotIn("ZQX", r.text)

    def test_only_local_requests_until_login_exists(self):
        remote = TestClient(make_app(), client=("10.0.0.5", 5000))
        r = remote.post("/api/c09/uploads", params=QS, content=self.data)
        self.assertEqual(r.status_code, 403)

    def test_db_not_configured(self):
        with mock.patch.object(api.db, "is_configured", return_value=False):
            self.assertEqual(self.post().status_code, 503)
