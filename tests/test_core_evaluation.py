"""공통 평가 틀(W05-06) 시험. 실행: uv run python -m pytest tests/test_core_evaluation.py"""
import tempfile
import unittest
from pathlib import Path

from app.services.evaluation.harness import Case, check_rule, evaluate, judge, load_cases


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

    def test_adapter_error_counted(self):
        def boom(_):
            raise RuntimeError("x")
        rep = evaluate("demo", [C("같음", ["a"])], boom)
        self.assertEqual((rep.passed, rep.errors), (0, 1))


if __name__ == "__main__":
    unittest.main()
