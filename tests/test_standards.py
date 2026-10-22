"""A-11 법령 개정 확인 · A-12 업무분장 변경 확인 · F-05 담당 부서 표 수정안 시험 (만든 글자로, DB 없이).
실행: uv run python -m pytest tests/test_standards.py
"""
import unittest

from app.services.standards.dept_draft import DELEGATED_TO, check_draft, make_drafts, proposal_text
from app.services.standards.duty_table import compare as duty_compare, parse
from app.services.standards.revision import compare as law_compare

OLD = """■ 시험 조례 [별표 1]
소  관
부  서
도로과
○ 도로에 관한 권한
1
 ㆍ 도로유지관리(국도 제외)
도로법 제31조
2
 ㆍ 가로등·보안등 설치 및 유지관리
도로법 제31조, 제50조
교통기획과
3
○ 불법 주ㆍ정차 단속 및 조치에 관한
   다음의 권한
 ㆍ 불법 주ㆍ정차 지도ㆍ단속
도로교통법 제32조 내지 제35조
"""

NEW = OLD.replace(" ㆍ 가로등·보안등 설치 및 유지관리\n도로법 제31조, 제50조\n", "") \
         .replace("도로과\n○ 도로에 관한 권한", "도로과\n○ 보도 내 불법 적치물 정비\n도로법 제74조\n○ 도로에 관한 권한") \
         .replace("도로교통법 제32조 내지 제35조", "도로교통법 제32조 내지 제36조")

JUR = [
    {"id": "JUR-04", "problem": "조도 부족", "dept": "각 구 건설과 도로조명팀", "related": "시 도로과", "status": "확인됨", "basis": "-"},
    {"id": "JUR-07", "problem": "불법 적치", "dept": "시 도로과 도로행정팀", "related": "각 구", "status": "확인됨", "basis": "-"},
    {"id": "JUR-09", "problem": "드론", "dept": "어딘가", "related": "-", "status": "확인됨", "basis": "-"},
]


class DutyTests(unittest.TestCase):
    def test_parse(self):
        d = parse(OLD)
        self.assertEqual([(x.dept, x.duty) for x in d], [
            ("도로과", "도로 > 도로유지관리(국도 제외)"),
            ("도로과", "도로 > 가로등·보안등 설치 및 유지관리"),
            ("교통기획과", "불법 주ㆍ정차 단속 및 조치 > 불법 주ㆍ정차 지도ㆍ단속"),
        ])
        self.assertEqual(d[1].basis, "도로법 제31조, 제50조")

    def test_compare(self):
        rep = duty_compare(parse(OLD), parse(NEW), "시험 조례 별표 1")
        kinds = sorted((c["change"], c["where"]) for c in rep["changes"])
        self.assertEqual(kinds, sorted([("근거 바뀜", "교통기획과"), ("없어진 사무", "도로과"), ("새 사무", "도로과")]))
        self.assertTrue(all(c["related"] for c in rep["changes"]))

    def test_moved_between_depts(self):
        moved = OLD.replace("교통기획과\n3\n", "주차지원과\n3\n")
        rep = duty_compare(parse(OLD), parse(moved))
        c = rep["changes"][0]
        self.assertEqual((c["change"], c["from_dept"], c["to_dept"]), ("부서 옮김", "교통기획과", "주차지원과"))
        self.assertEqual(rep["depts"], {"new": ["주차지원과"], "gone": ["교통기획과"]})


class DraftTests(unittest.TestCase):
    def test_drafts_from_delegation_annex(self):
        rep = duty_compare(parse(OLD), parse(NEW), "시험 조례 별표 1")
        drafts = {d["jur_id"]: d for d in make_drafts(rep["changes"], JUR, "시험 조례 별표 1")}
        self.assertEqual(set(drafts), {"JUR-04", "JUR-07"})                    # 드론은 걸리지 않음
        self.assertEqual(drafts["JUR-04"]["to"], "도로과")                      # 위임 해제 → 시 소관 부서
        self.assertEqual(drafts["JUR-07"]["to"], DELEGATED_TO)                  # 새 위임 → 각 구 (확인 필요)
        self.assertTrue(all(d["needs_review"] for d in drafts.values()))
        with self.assertRaises(ValueError):
            check_draft(drafts["JUR-07"])                                        # 사람이 to를 고치기 전에는 못 올림
        fixed = dict(drafts["JUR-07"], to="수정구 건설과 도로관리팀")
        check_draft(fixed)
        self.assertLessEqual(len(proposal_text(fixed)), 255)


class LawRevisionTests(unittest.TestCase):
    def c(self, art, text, eff="2026-07-01", law="도로교통법"):
        return {"law_name": law, "article": art, "article_title": "t", "text": text, "effective": eff, "status": "시행 중"}

    def test_compare_articles(self):
        old = [self.c("제32조", "가"), self.c("제33조", "나"), self.c("제34조", "다")]
        new = [self.c("제32조", "가 바뀜", "2027-01-01"), self.c("제33조", "나", "2027-01-01"),
               self.c("제35조", "라", "2027-01-01")]
        crit = [{"criterion_id": "L17", "이름": "도로교통법", "조항·만든 곳": "제32조~제35조", "RADAR에서 쓴 곳": "T18"},
                {"criterion_id": "L15", "이름": "도로교통법", "조항·만든 곳": "제12조", "RADAR에서 쓴 곳": "T01"}]
        rep = law_compare(old, new, crit)
        got = sorted((c["where"].split("(")[0], c["change"]) for c in rep["changes"])
        self.assertEqual(got, [("제32조", "바뀜"), ("제34조", "없어짐"), ("제35조", "새 조문")])
        self.assertEqual(rep["laws"][0]["status"], "시행일 바뀜")
        self.assertEqual(rep["summary"]["criteria_to_check"], ["L17"])         # 제12조(L15)는 직접 걸리지 않음

    def test_same_is_quiet(self):
        old = [self.c("제32조", "가")]
        self.assertEqual(law_compare(old, [dict(old[0])])["summary"]["laws_changed"], 0)

    def test_new_and_gone_law(self):
        rep = law_compare([self.c("제1조", "a", law="옛법")], [self.c("제1조", "b", law="새법")])
        self.assertEqual(sorted(l["status"] for l in rep["laws"]), ["빠짐", "새로 들어옴"])


if __name__ == "__main__":
    unittest.main()


class LinkAndSaveTests(unittest.TestCase):
    def test_link_jurisdiction(self):
        from app.services.standards.dept_draft import link_jurisdiction
        rows = [{"id": "JUR-05", "problem": "가로등·보안등 문제", "basis": "사무위임 조례 별표1"},
                {"id": "JUR-06", "problem": "불법주정차", "basis": "도로교통법 제32조·제35조"}]
        ch = [{"kind": "업무분장", "duty": "도로 > 가로등·보안등 설치 및 유지관리"},
              {"kind": "법령", "name": "도로교통법"}]
        link_jurisdiction(ch, rows)
        self.assertEqual([c["related_jur"] for c in ch], [["JUR-05"], ["JUR-06"]])

    def test_rows_to_save_adds_law_level(self):
        from app.services.standards.revision import rows_to_save
        rep = {"changes": [], "laws": [{"name": "도로법", "status": "시행일 바뀜", "old_effective": "2026-09-18",
                                        "new_effective": "2027-03-23", "criteria": []}]}
        rows = rows_to_save(rep)
        self.assertEqual((rows[0]["change"], rows[0]["where"], rows[0]["date"]), ("시행일 바뀜", "법령 전체", "2027-03-23"))


class StandardsApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.core import access_audit
        from app.core.auth import make_token
        from app.main import app
        from app.services.standards import repository

        class FakeRepo(repository.StandardsRepository):
            def __init__(self):
                self.props, self.seen = [], []

            def jurisdiction(self):
                return [{"id": "JUR-05", "problem": "가로등", "dept": "수정구: 도로조명팀", "related": None, "status": "확인됨",
                         "basis": "-", "mvp": "MVP", "note": None, "setting_version_id": None,
                         "depts": [{"gu_name": "수정구", "condition_text": None, "dept_name": "도로조명팀", "org_level": "구"}]}]

            def list_changes(self, unseen_only, limit):
                return []

            def mark_seen(self, cid, uid):
                self.seen.append(cid)
                return cid == 1

            def submit_proposal(self, label, content, by):
                self.props.append((label, content, by))
                return 7

        class Audit(access_audit.AuditStore):
            def insert(self, *a):
                pass

        self.repo = FakeRepo()
        repository.set_repository(self.repo)
        access_audit.set_store(Audit())
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")
        tok, _ = make_token({"user_id": 3, "login_id": "operator", "role": "operator", "gu": None})
        self.h = {"Authorization": "Bearer " + tok}

    def tearDown(self):
        from app.core import access_audit
        from app.services.standards import repository
        repository.set_repository(repository.StandardsRepository())
        access_audit.set_store(access_audit.AuditStore())

    def test_jurisdiction_and_guard(self):
        self.assertEqual(self.c.get("/api/standards/jurisdiction").status_code, 401)
        j = self.c.get("/api/standards/jurisdiction", headers=self.h).json()["jurisdiction"]
        self.assertEqual(j[0]["depts"][0]["deptName"], "도로조명팀")

    def test_submit_draft(self):
        body = {"jurId": "JUR-05", "problem": "가로등", "from": "수정구 도로조명팀", "to": "시 도로과 도로관리팀",
                "basis": "성남시 사무위임 조례 별표 1"}
        r = self.c.post("/api/standards/drafts", json=body, headers=self.h)
        self.assertEqual((r.status_code, r.json()["settingVersionId"]), (200, 7))
        bad = dict(body, to="각 구 (구청장 위임, 담당 팀 확인 필요)")
        self.assertEqual(self.c.post("/api/standards/drafts", json=bad, headers=self.h).status_code, 400)

    def test_seen(self):
        self.assertEqual(self.c.post("/api/standards/changes/1/seen", headers=self.h).status_code, 200)
        self.assertEqual(self.c.post("/api/standards/changes/9/seen", headers=self.h).status_code, 404)
