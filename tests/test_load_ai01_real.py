"""진짜 AI-01 함수(app/services/ai01/refine.py)와 적재를 이은 시험.

AI-01이 합쳐진 트리에서만 돈다 (없으면 건너뜀). AI-01 시험처럼 이름 모델과 LLM은 가짜로 바꾸므로 torch·Ollama 없이 돈다.
"""
import unittest
from unittest import mock

try:
    from app.core.llm import LlmResult
    from app.services.ai01 import classify as cls, masking, ptype, refine, summarize as summ
    HAVE_AI01 = True
except ImportError:
    HAVE_AI01 = False

from app.core import job_run
from app.services.load import ai01_port as port
from app.services.load.pipeline import run_load
from app.services.load.store import MemoryStore
from tests.test_load_api import MemoryJobStore
from tests.test_load_fixtures import GRID, general, meta, spp, xlsx

FILE = "민원 상세정보 현황-20261022190720.xlsx"
LONG = "○○로 인도에 매일 차가 주차합니다. " * 20 + "연락처 010-1234-5678"            # 200자를 넘어 요약 모델을 거침


def fake_ner(seg):
    return []


def llm(data):
    return LlmResult(ok=True, task="t", route="internal", model="m", data=data)


@unittest.skipUnless(HAVE_AI01, "AI-01 함수가 없는 트리 (합친 뒤에 돈다)")
class RealAi01Tests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(GRID)
        self.jobs = MemoryJobStore()
        job_run.set_store(self.jobs)
        self.summarize = mock.Mock(return_value=llm({"summary": "○○로 인도에 차가 매일 주차되어 통행이 어렵습니다."}))
        self.classify = mock.Mock(return_value=llm({"relevance": "관련", "confidence": 0.9, "reason": "보행 공간 불법 주정차: 인도 주차"}))
        self.patches = [
            mock.patch.object(masking, "_ner", return_value=fake_ner),
            mock.patch.object(masking, "common_words", return_value=frozenset()),
            mock.patch.object(summ, "call_llm", self.summarize),
            mock.patch.object(cls, "call_llm", self.classify),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        job_run.set_store(job_run.JobStore())

    def load(self, rows):
        return run_load(xlsx(rows), FILE, meta(), self.store)

    def test_default_backend_is_the_real_function(self):
        self.assertEqual(port.resolve_backend().kind, "ai01")

    def test_ok_results_fill_the_class_columns(self):
        res = self.load([spp(1), general(2, body=LONG)])
        self.assertEqual((res.ai.backend, res.ai.ok, res.ai.error), ("ai01", 2, 0))
        rows = list(self.store.complaints.values())
        for c in rows:
            self.assertTrue(c["masked_summary"] and c["relevance"] and c["class_reason"], c["raw_position"])
            self.assertIsNotNone(c["class_confidence"])
            if c["relevance"] == "보행안전 관련":
                self.assertIn(c["ped_type"], ptype.TYPES + (None,))           # 관련이면 유형 9개 중 하나(정하지 못하면 None)
            else:
                self.assertIsNone(c["ped_type"])                                # 관련이 아니면 유형을 비운다
            self.assertLessEqual(len(c["relevance"]), 10)                       # 79 relevance VARCHAR(10)
        self.assertFalse(any("AI-01" in w for w in res.warnings))

    def test_class_method_comes_from_the_real_decision_path(self):
        self.load([spp(1), general(2, body=LONG)])
        rows = {c["raw_position"].rsplit(" ", 1)[1]: c for c in self.store.complaints.values()}
        self.assertIn(rows["1"]["class_method"], ("규칙", "AI"))              # 신고 분류가 있는 안전신문고: 규칙 또는 모델
        self.assertEqual(rows["2"]["class_method"], "AI")                     # 신고 분류 없는 일반 민원: 모델(가짜 LLM)
        self.assertEqual(rows["2"]["class_confidence"], 0.9)

    def test_upload_id_reaches_the_ai01_job_run(self):
        res = self.load([general(1, body=LONG)])
        runs = [r for r in self.jobs.runs.values() if r["kind"] == "분류"]
        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0]["module"], runs[0]["ref_table"], runs[0]["ref_id"]), ("AI-01", "data_upload", str(res.upload_id)))

    def test_pii_is_gone_from_everything_stored(self):
        res = self.load([general(1, body=LONG), general(2, body=LONG + " 또 010-9999-8888")])
        dump = repr(self.store.complaints) + repr(self.store.changes) + repr(self.store.uploads) + repr(self.jobs.runs) + repr(self.jobs.logs)
        for leak in ("1234-5678", "9999-8888", "010-1234"):
            self.assertNotIn(leak, dump)
        self.assertEqual(res.counts.new, 2)

    def test_mask_failure_keeps_ai_columns_empty_and_load_going(self):
        with mock.patch.object(masking, "left_kinds", return_value=["휴대전화"]):
            res = self.load([general(1, body=LONG)])
        c = next(iter(self.store.complaints.values()))
        self.assertEqual((c["masked_summary"], c["relevance"], c["class_reason"]), (None, None, "가림 실패"))
        self.assertEqual((res.ai.mask_failed, res.counts.new), (1, 1))
        self.classify.assert_not_called()                                       # 가림에 실패한 민원은 분류로 보내지 않음 (C-03)

    def test_model_failure_is_error_and_load_continues(self):
        self.summarize.return_value = LlmResult(ok=False, task="t", error_code="internal_unavailable")
        res = self.load([general(1, body=LONG)])
        c = next(iter(self.store.complaints.values()))
        self.assertEqual((c["masked_summary"], c["relevance"]), (None, None))
        self.assertEqual((res.ai.error, res.counts.new), (1, 1))
        self.assertTrue(any("오류 1건" in w for w in res.warnings))

    def test_second_upload_does_not_call_the_models_again(self):
        self.load([general(1, body=LONG)])
        calls = (self.summarize.call_count, self.classify.call_count)
        res = self.load([general(1, body=LONG)])
        self.assertEqual((self.summarize.call_count, self.classify.call_count), calls)
        self.assertEqual((res.counts.existing, res.ai.attempted), (1, 0))


if __name__ == "__main__":
    unittest.main()
