"""F-05 AI 추출 시험 (실제 LLM 없이). 실행: uv run python -m pytest tests/test_f05_extract.py"""
import unittest
from types import SimpleNamespace

from app.services.standards.dept_draft import make_drafts
from app.services.standards.extract_llm import extract, verify

SRC = "분당구 건설과 도로관리팀: 국도3호선 구간 보도 유지관리 및 보수"
ROWS = [
    {"id": "JUR-02", "problem": "보도 파손·단차·점자블록", "dept": "분당구: 건설과 보도관리팀",
     "depts": [{"gu_name": "분당구", "condition_text": None, "dept_name": "건설과 보도관리팀"},
               {"gu_name": None, "condition_text": "국도3호선·국지도57·23호선", "dept_name": "시 도로과 도로관리팀"}]},
    {"id": "JUR-05", "problem": "가로등·보안등 문제", "dept": "분당구: 건설과 도로조명팀", "depts": []},
]
CHANGE = {"kind": "업무분장", "change": "부서 옮김", "duty": "보도 유지관리 및 보수", "where": "분당구 건설과",
          "from_dept": "분당구 건설과 보도관리팀", "to_dept": "분당구 건설과 도로관리팀",
          "before": "분당구 건설과 보도관리팀: 보도 유지관리 및 보수", "after": SRC}


class VerifyTests(unittest.TestCase):
    def test_keeps_only_text_in_source(self):
        items = verify([{"duty": "보도 유지관리 및 보수", "dept": "분당구 건설과 도로관리팀", "road_type": "국도"},
                        {"duty": "가로등 관리", "dept": "도로조명팀", "road_type": None},          # 문장에 없는 업무 → 버림
                        {"duty": "보도 유지관리", "dept": "시 도로과", "road_type": "고속도로"}], SRC)   # 없는 부서·목록 밖 도로 → 비움
        self.assertEqual(items[0], {"duty": "보도 유지관리 및 보수", "dept": "분당구 건설과 도로관리팀", "road_type": "국도"})
        self.assertEqual(len(items), 2)
        self.assertEqual((items[1]["dept"], items[1]["road_type"]), (None, None))

    def test_falls_back_when_llm_not_ready(self):
        not_ready = lambda *a, **k: SimpleNamespace(ok=False, error_code="unknown_task")
        self.assertIsNone(extract(SRC, call=not_ready))
        ok = lambda *a, **k: SimpleNamespace(ok=True, model="exaone3.5:7.8b",
                                             data={"items": [{"duty": "보도 유지관리 및 보수", "dept": None, "road_type": "국도"}]})
        r = extract(SRC, call=ok)
        self.assertEqual((r["model"], r["items"][0]["road_type"]), ("exaone3.5:7.8b", "국도"))


class DraftTests(unittest.TestCase):
    def test_rule_when_no_ai(self):
        d = make_drafts([CHANGE], ROWS, "분당구 업무분장", delegation_annex=False, use_ai=False)
        self.assertEqual([(x["jur_id"], x["method"], x["to"]) for x in d], [("JUR-02", "규칙", "분당구 건설과 도로관리팀")])

    def test_ai_adds_road_type_and_evidence(self):
        fake = lambda text: {"model": "exaone3.5:7.8b",
                             "items": [{"duty": "국도3호선 구간 보도 유지관리 및 보수", "dept": "분당구 건설과 도로관리팀", "road_type": "국도"}]}
        d = make_drafts([CHANGE], ROWS, "분당구 업무분장", delegation_annex=False, extractor=fake)[0]
        self.assertEqual((d["jur_id"], d["method"], d["road_type"]), ("JUR-02", "AI (exaone3.5:7.8b)", "국도"))
        self.assertEqual(d["evidence"]["ai"]["road_condition"], "국도3호선·국지도57·23호선")   # 표의 나뉘는 조건과 맞음
        self.assertEqual(d["evidence"]["after"], SRC)                                             # 근거는 원문 그대로
        self.assertTrue(d["needs_review"])

    def test_ai_unavailable_falls_back_to_rule(self):
        d = make_drafts([CHANGE], ROWS, "분당구 업무분장", delegation_annex=False, extractor=lambda text: None)
        self.assertEqual(d[0]["method"], "규칙")


if __name__ == "__main__":
    unittest.main()
