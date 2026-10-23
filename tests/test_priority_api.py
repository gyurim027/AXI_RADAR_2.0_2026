"""우선순위 결과 조회 API (77·78·82) 시험. 실제 DB 없이 돈다.
실행: uv run python -m pytest tests/test_priority_api.py
"""
import unittest
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.auth import make_token
from app.main import app
from app.services.priority import repository as pr

RUN = {"run_id": 1, "build_id": "B1", "rule_version": "TEST", "created_at": datetime(2026, 10, 23, 9), "note": None}
ROWS = [
    {"gid": "다사01", "gu": "수정구", "selected_yn": "Y", "score": Decimal("81.5000"), "rank_no": 1},
    {"gid": "다사02", "gu": "분당구", "selected_yn": "N", "score": None, "rank_no": None},     # 미산출
    {"gid": "다사03", "gu": None, "selected_yn": None, "score": None, "rank_no": None},        # 구 없는 격자
]


def _row(r):
    base = {k: None for k in pr.CANDIDATE_COLS}
    return {**base, "run_id": 1, **r}


class MemoryRepo(pr.PriorityRepository):
    def list_runs(self, limit):
        return [dict(RUN, candidate_cnt=3, selected_cnt=1, scored_cnt=1)]

    def get_run(self, run_id):
        return dict(RUN) if run_id == 1 else None

    def list_candidates(self, run_id, gus, include_no_gu, selected, limit, offset):
        rows = [_row(r) for r in ROWS]
        rows = [r for r in rows if (r["gu"] is None and include_no_gu) or
                (r["gu"] is not None and (gus is None or r["gu"] in gus))]
        if selected:
            rows = [r for r in rows if r["selected_yn"] == selected]
        return rows[offset:offset + limit], len(rows)

    def get_candidate(self, run_id, gid):
        for r in ROWS:
            if run_id == 1 and r["gid"] == gid:
                return dict(_row(r), actions=[{"item_id": "CK-12", "action_text": "점검", "dept_text": "도로과",
                                                "basis_text": "도로법", "created_at": datetime(2026, 10, 23, 9)}])
        return None


def _h(role, gu=None):
    tok, _ = make_token({"user_id": 9, "login_id": role, "role": role, "gu": gu})
    return {"Authorization": f"Bearer {tok}"}


class PriorityApiTests(unittest.TestCase):
    def setUp(self):
        pr.set_repository(MemoryRepo())
        self.c = TestClient(app)

    def tearDown(self):
        pr.set_repository(pr.PriorityRepository())

    def test_login_needed(self):
        self.assertEqual(self.c.get("/api/priority/runs").status_code, 401)

    def test_runs(self):
        j = self.c.get("/api/priority/runs", headers=_h("city")).json()
        self.assertEqual(j["runs"][0]["runId"], 1)
        self.assertEqual((j["runs"][0]["candidateCnt"], j["runs"][0]["scoredCnt"]), (3, 1))

    def test_null_stays_null(self):
        j = self.c.get("/api/priority/runs/1/candidates", headers=_h("operator")).json()
        self.assertEqual(j["total"], 3)
        first, unscored = j["candidates"][0], j["candidates"][1]
        self.assertEqual((first["score"], first["scoreStatus"]), (81.5, "산출"))
        self.assertIsNone(unscored["score"])                         # 0으로 바꾸지 않음
        self.assertIsNone(unscored["rankNo"])
        self.assertEqual(unscored["scoreStatus"], "미산출")
        self.assertEqual(unscored["details"], {"stored": False, "domainScores": None, "indicatorContributions": None,
                                               "unevaluatedReasons": None, "confidenceGrade": None,
                                               "scoreExcludingAccidents": None})

    def test_district_sees_own_gu_only(self):
        j = self.c.get("/api/priority/runs/1/candidates", headers=_h("district", "수정구")).json()
        self.assertEqual([c["gid"] for c in j["candidates"]], ["다사01"])
        r = self.c.get("/api/priority/runs/1/candidates?gu=분당구", headers=_h("district", "수정구"))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.c.get("/api/priority/runs/1/candidates/다사02",
                                    headers=_h("district", "수정구")).status_code, 403)
        self.assertEqual(self.c.get("/api/priority/runs/1/candidates/다사03",          # 구 없는 격자
                                    headers=_h("district", "수정구")).status_code, 403)

    def test_filters_and_detail(self):
        j = self.c.get("/api/priority/runs/1/candidates?selected=Y", headers=_h("city")).json()
        self.assertEqual([c["gid"] for c in j["candidates"]], ["다사01"])
        d = self.c.get("/api/priority/runs/1/candidates/다사01", headers=_h("city")).json()
        self.assertEqual(d["actions"][0]["itemId"], "CK-12")
        self.assertEqual(d["gu"], "수정구")

    def test_bad_input(self):
        self.assertEqual(self.c.get("/api/priority/runs/abc/candidates", headers=_h("city")).status_code, 422)
        self.assertEqual(self.c.get("/api/priority/runs/9/candidates", headers=_h("city")).status_code, 404)
        self.assertEqual(self.c.get("/api/priority/runs/1/candidates/없음", headers=_h("city")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
