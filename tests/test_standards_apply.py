"""F-05 반영 함수(승인된 62 → 87·88) 시험. DB 없이 글자 처리와 막는 규칙만 본다.
실행: uv run python -m pytest tests/test_standards_apply.py
"""
import unittest

from app.services.standards.apply import ApplyError, _check, parse_piece, parse_proposal, plan, table_label
from app.services.standards.dept_draft import proposal_text

DEPTS = [
    {"gu_name": "수정구", "condition_text": None, "dept_name": "건설과 도로관리팀", "org_level": "구"},
    {"gu_name": "수정구", "condition_text": "수정구 그 밖의 동", "dept_name": "건설과 도로관리TF팀", "org_level": "구"},
    {"gu_name": None, "condition_text": "국도3호선", "dept_name": "시 도로과 도로관리팀", "org_level": "시"},
]
BEFORE = table_label(DEPTS)


class ApplyTests(unittest.TestCase):
    def test_label_round_trip(self):
        self.assertEqual(BEFORE, "수정구: 건설과 도로관리팀 / 수정구 그 밖의 동: 건설과 도로관리TF팀 / 국도3호선: 시 도로과 도로관리팀")

    def test_parse_proposal(self):
        text = proposal_text({"jur_id": "JUR-02", "problem": "보도 파손", "from": BEFORE, "to": "중원구: 건설과", "basis": "별표 1"})
        self.assertEqual(parse_proposal(text, "보도 파손"), ("JUR-02", BEFORE, "중원구: 건설과"))
        with self.assertRaises(ApplyError):
            parse_proposal(text, "다른 문제")                           # 문제 유형이 바뀜
        with self.assertRaises(ApplyError):
            parse_proposal(text[:100] + "…", "보도 파손")                # 255자에서 잘린 글자

    def test_plan_keeps_unchanged_rows(self):
        after = "수정구 그 밖의 동: 건설과 도로관리TF팀 / 분당구: 건설과 보도관리팀"
        rows = plan(DEPTS, after)
        self.assertEqual(rows[0]["condition_text"], "수정구 그 밖의 동")
        self.assertEqual((rows[0]["gu_name"], rows[0]["org_level"], rows[0]["kept"]), ("수정구", "구", True))
        self.assertEqual((rows[1]["gu_name"], rows[1]["dept_name"], rows[1]["kept"]), ("분당구", "건설과 보도관리팀", False))
        self.assertEqual([r["sort_no"] for r in rows], [1, 2])

    def test_parse_piece(self):
        self.assertEqual(parse_piece("근거 없음")["dept_name"], None)
        p = parse_piece("보도 신설·확장: 시 도로과")
        self.assertEqual((p["gu_name"], p["condition_text"], p["dept_name"]), (None, "보도 신설·확장", "시 도로과"))

    def test_blocks(self):
        sv = {"setting_version_id": 7, "approval_status": "승인"}
        jur = {"setting_version_id": None}
        self.assertIsNone(_check(sv, jur, DEPTS, BEFORE, "중원구: 건설과", True))
        self.assertEqual(_check(sv, {"setting_version_id": 7}, DEPTS, BEFORE, "중원구: 건설과", True), "already")
        cases = [
            (dict(sv, approval_status="제안"), BEFORE, "중원구: 건설과", "not_approved"),
            (sv, "예전 표", "중원구: 건설과", "table_changed"),
            (sv, BEFORE, "각 구(확인 필요)", "needs_review"),
            (sv, BEFORE, BEFORE, "no_change"),
        ]
        for s, before, after, code in cases:
            with self.assertRaises(ApplyError) as e:
                _check(s, jur, DEPTS, before, after, True)
            self.assertEqual(e.exception.code, code)


if __name__ == "__main__":
    unittest.main()
