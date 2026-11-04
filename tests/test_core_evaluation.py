"""공통 평가 틀(W05-06) 시험. 실행: uv run python -m pytest tests/test_core_evaluation.py"""
import tempfile
import unittest
from pathlib import Path

from app.services.evaluation.harness import Case, check_rule, evaluate, judge, load_cases, summary_text


def C(rule, exp=(), inp="x"):
    return Case("01", inp, list(exp), check_rule(rule))


class HarnessTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(judge(C("같음", ["관련"]), "관련")[0], True)
        self.assertEqual(judge(C("같음", ["관련"]), ["비관련", "관련"])[0], False)       # 목록이면 1등만
        self.assertEqual(judge(C("포함", ["제32조", "제33조"]), ["도로교통법 제32조", "제33조"])[0], True)
        self.assertEqual(judge(C("포함", ["제35조"]), ["제32조"])[0], False)
        self.assertEqual(judge(C("안 들어감", ["010-"]), "가린 문장 [휴대전화]")[0], True)
        self.assertEqual(judge(C("안 들어감", ["홍길동"]), "홍길동 신고")[0], False)
        self.assertEqual(judge(C("안 들어감", ["위험하다"]), None)[0], False)          # 빈 결과는 통과 아님
        self.assertEqual(judge(C("안 들어감", ["위험하다"]), "")[0], False)
        self.assertEqual(judge(C("3등 안", ["유효폭"]), ["a", "b", "3-2 유효폭", "d"])[0], True)
        self.assertEqual(judge(C("2등 안", ["유효폭"]), ["a", "b", "3-2 유효폭"])[0], False)
        self.assertEqual(judge(C("못 찾음"), [])[0], True)
        self.assertEqual(judge(C("못 찾음"), None)[0], True)
        self.assertEqual(judge(C("못 찾음"), ["뭔가"])[0], False)

    def test_not_rule(self):                                                       # AI-03 "이 gid를 내면 오답"
        self.assertEqual(judge(C("아님", ["다사01"]), "다사02")[0], True)
        self.assertEqual(judge(C("아님", ["다사01"]), "다사01")[0], False)
        self.assertEqual(judge(C("아님", ["다사01"]), None)[0], True)                  # 못 찾은 건 오답 아님

    def test_wrong_link_and_find_rate(self):
        cases = [C("같음", ["g1"], "a"), C("같음", ["g2"], "b"), C("같음", ["g3"], "c"),
                 C("아님", ["g9"], "d"), C("못 찾음", [], "e")]
        answers = {"a": "g1", "b": "gX", "c": None, "d": "g9", "e": "g5"}
        rep = evaluate("ai03", cases, lambda s: answers[s])
        self.assertEqual((rep.answered, rep.answered_wrong), (4, 3))     # b·d·e는 냈는데 틀림
        self.assertEqual(rep.wrong_link_rate, 75.0)                     # 분모 = 결과 낸 수 (전체 아님)
        self.assertEqual((rep.found, rep.should_find, rep.find_rate), (2, 3, 66.7))

    def test_text_not_found_counted_as_empty(self):
        """AI-03 상태 평가처럼 '못 찾음'을 글자로 돌려주는 어댑터 (10/26): --empty로 세는 값만 바꾸고 판정은 그대로"""
        cases = [C("같음", ["성공"], "a"), C("같음", ["성공"], "b"), C("같음", ["못 찾음"], "c"), C("같음", ["성공"], "d")]
        answers = {"a": "성공", "b": "못 찾음", "c": "못 찾음", "d": "도로 단위"}
        plain = evaluate("st", cases, lambda s: answers[s])
        self.assertEqual((plain.passed, plain.answered, plain.answered_wrong), (2, 4, 2))   # 놓친 b가 '오연결'로 보임
        rep = evaluate("st", cases, lambda s: answers[s], empty=["못 찾음"])
        self.assertEqual(rep.passed, 2)                                    # 판정은 같음 (c는 '못 찾음'이 나와야 맞음)
        self.assertEqual((rep.answered, rep.answered_wrong, rep.wrong_link_rate), (2, 1, 50.0))   # d만 진짜 오연결
        self.assertEqual((rep.found, rep.should_find), (2, 4))
        self.assertIn("'못 찾음'은 결과 없음으로 셈", summary_text(rep))

    def test_spacing_and_case_ignored(self):
        self.assertTrue(judge(C("같음", ["EPSG 5179"]), "epsg  5179")[0])

    def test_bad_rule(self):
        with self.assertRaises(ValueError):
            check_rule("대충 맞음")

    def test_load_csv_and_evaluate(self):
        csv = "case_id,입력,기대 답,맞음 기준,메모\n01,a,A,같음,\n02,b,,못 찾음,\n03,c,X | Y,포함,\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cases.csv"
            p.write_text(csv, encoding="utf-8-sig")
            cases = load_cases(p)
        self.assertEqual([c.expected for c in cases], [["A"], [], ["X", "Y"]])
        answers = {"a": "A", "b": None, "c": "X만"}
        rep = evaluate("demo", cases, lambda s: answers[s])
        self.assertEqual((rep.total, rep.passed, rep.rate), (3, 2, 66.7))
        self.assertEqual(rep.failed[0]["case_id"], "03")

    def test_header_variants_and_note_shown(self):
        csv = "Case_ID,입력,기대 답*,맞음기준,메모 (선택)\n01,a,A,같음,주정차 단속\n02,b,B,같음,\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cases.csv"
            p.write_text(csv, encoding="utf-8-sig")
            cases = load_cases(p)
        self.assertEqual([(c.case_id, c.expected, c.note) for c in cases], [("01", ["A"], "주정차 단속"), ("02", ["B"], "")])
        rep = evaluate("demo", cases, lambda s: "틀림")
        self.assertEqual([f["note"] for f in rep.failed], ["주정차 단속", ""])
        text = summary_text(rep)
        self.assertIn("— 메모: 주정차 단속", text)
        self.assertEqual(text.count("메모:"), 1)                                   # 빈 메모는 안 보임

    def test_note_column_optional(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cases.csv"
            p.write_text("입력,기대 답,맞음 기준\na,A,같음\n", encoding="utf-8-sig")
            self.assertEqual(load_cases(p)[0].note, "")

    def test_adapter_error_counted(self):
        def boom(_):
            raise RuntimeError("x")
        rep = evaluate("demo", [C("같음", ["a"])], boom)
        self.assertEqual((rep.passed, rep.errors), (0, 1))


if __name__ == "__main__":
    unittest.main()
