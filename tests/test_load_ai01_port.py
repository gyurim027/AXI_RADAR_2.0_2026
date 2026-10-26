"""적재 4단계 AI-01 자리 시험: 인자 전달 · 진짜 함수 해석 · 요약 개인정보 강등 · 경고 문구 (AI-01 본체 없이 돈다)."""
import builtins
import unittest
from unittest import mock

from app.services.load import ai01_port as port
from app.services.load.ai01_stub import Ai01Result, ComplaintInput, refine_complaints as stub_refine
from app.services.load.pipeline import run_load
from app.services.load.reader import RawRow
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import GRID, general, meta, spp, xlsx

FILE = "민원 상세정보 현황-20261022190720.xlsx"


def ok(item, summary="요약", model="mask-1+sum-2+cls-2"):
    return Ai01Result(item.complaint_id, "ok", summary, "보행안전 관련", None, 0.9, "근거", model=model)


def rows_and_records(n=2):
    rows = [RawRow(i, f"제목{i}", "2025-11-03", "-", "기타", f"본문{i}") for i in range(1, n + 1)]
    recs = [dict(complaint_id=f"C00000000000{i}", source_type="일반 민원", report_type_raw=None,
                 **{c: None for c in port.AI_COLS}) for i in range(1, n + 1)]
    return rows, recs


class CallTests(unittest.TestCase):
    def test_kwargs_only_for_functions_that_accept_them(self):
        seen = {}

        def one(items):
            seen["one"] = {}
            return []

        def named(items, upload_id=None, request_id=None):
            seen["named"] = dict(upload_id=upload_id, request_id=request_id)
            return []

        def var(items, **kw):
            seen["var"] = kw
            return []

        for fn in (one, named, var):
            port._call(fn, [], 7, "rid")
        self.assertEqual(seen, {"one": {}, "named": dict(upload_id=7, request_id="rid"), "var": dict(upload_id=7, request_id="rid")})

    def test_none_values_are_not_passed(self):
        got = {}
        port._call(lambda items, **kw: got.update(kw) or [], [], None, None)
        self.assertEqual(got, {})

    def test_stub_accepts_extra_arguments(self):
        out = stub_refine([ComplaintInput("C1", "일반 민원", "t", "b", None)], upload_id=3, request_id="r")
        self.assertEqual(out[0].model, "stub")

    def test_nothing_to_send_means_no_call(self):
        called = []
        s = port.apply_ai01([], [], lambda items: called.append(1) or [])
        self.assertEqual((called, s.attempted), ([], 0))


def import_fails(exc):
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "app.services.ai01.refine":
            raise exc
        return real(name, *a, **k)
    return mock.patch("builtins.__import__", side_effect=fake)


class ResolveTests(unittest.TestCase):
    def test_custom_function_is_kept(self):
        f = lambda items: []
        b = port.resolve_backend(f)
        self.assertEqual((b.kind, b.refine), ("custom", f))

    def test_ai01_not_merged_yet_means_stub_without_reason(self):
        with import_fails(ModuleNotFoundError("x", name="app.services.ai01.refine")):
            b = port.resolve_backend()
        self.assertEqual((b.kind, b.unavailable), ("stub", None))

    def test_missing_dependency_means_stub_with_reason(self):
        with import_fails(ModuleNotFoundError("x", name="app.core.llm")):
            b = port.resolve_backend()
        self.assertEqual((b.kind, b.unavailable), ("stub", "app.core.llm"))
        with import_fails(ImportError("깨짐")):
            b = port.resolve_backend()
        self.assertEqual((b.kind, b.unavailable), ("stub", "ImportError"))       # 예외 글자는 남기지 않고 종류만


class DemotionTests(unittest.TestCase):
    def test_only_the_row_with_leftover_pii_is_demoted(self):
        rows, recs = rows_and_records(2)

        def refine(items):
            return [ok(items[0], summary="연락처 010-1234-5678 로 연락 바람"), ok(items[1], summary="인도에 주차")]
        s = port.apply_ai01(rows, recs, refine)
        bad, good = recs
        self.assertEqual([bad[c] for c in port.AI_COLS], [None, None, None, None, "가림 실패"])
        self.assertEqual((good["masked_summary"], good["relevance"]), ("인도에 주차", "보행안전 관련"))
        self.assertEqual((s.ok, s.mask_failed, s.error), (1, 1, 0))

    def test_load_continues_when_one_summary_leaks(self):
        store = MemoryStore(GRID)

        def refine(items):
            return [ok(i, summary="차량 12가3456 신고" if k == 0 else "인도에 주차") for k, i in enumerate(items)]
        res = run_load(xlsx([spp(1), general(2), general(3)]), FILE, meta(), store, refine=refine)
        self.assertEqual(res.counts.new, 3)                                     # 파일 전체가 실패하지 않음
        by = {c["source_receipt_no"] or c["raw_position"]: c for c in store.complaints.values()}
        first = by["SPP-2511-ABC0001"]
        self.assertEqual((first["masked_summary"], first["class_reason"]), (None, "가림 실패"))
        self.assertEqual(sum(1 for c in store.complaints.values() if c["masked_summary"] == "인도에 주차"), 2)
        self.assertTrue(any("가림 실패 1건" in w for w in res.warnings))


class WarningTests(unittest.TestCase):
    def load(self, backend):
        store = MemoryStore(GRID)
        with mock.patch.object(port, "resolve_backend", return_value=backend):
            return run_load(xlsx([spp(1), general(2)]), FILE, meta(), store)

    def test_stub_without_reason(self):
        res = self.load(port.Backend(stub_refine, ComplaintInput, "stub"))
        self.assertEqual([w for w in res.warnings if "AI-01" in w], ["AI-01 함수가 아직 연결되지 않아 AI-01 칸을 채우지 않았습니다"])

    def test_stub_with_reason(self):
        res = self.load(port.Backend(stub_refine, ComplaintInput, "stub", unavailable="app.core.llm"))
        self.assertEqual([w for w in res.warnings if "AI-01" in w], ["AI-01을 불러오지 못해 AI-01 칸을 채우지 않았습니다"])

    def test_failures_and_errors_are_counted(self):
        def refine(items):
            return [Ai01Result(items[0].complaint_id, "mask_failed", model="m"), Ai01Result(items[1].complaint_id, "error", model="m")]
        res = self.load(port.Backend(refine, ComplaintInput, "ai01"))
        self.assertEqual([w for w in res.warnings if "AI-01" in w], ["AI-01: 가림 실패 1건, 오류 1건은 AI-01 칸을 비워 두었습니다"])

    def test_clean_run_has_no_ai01_warning(self):
        res = self.load(port.Backend(lambda items: [ok(i) for i in items], ComplaintInput, "ai01"))
        self.assertFalse(any("AI-01" in w for w in res.warnings))

    def test_upload_and_request_ids_reach_the_function(self):
        seen = {}

        def refine(items, upload_id=None, request_id=None):
            seen.update(upload_id=upload_id, request_id=request_id)
            return [ok(i) for i in items]
        store = MemoryStore(GRID)
        res = run_load(xlsx([general(1)]), FILE, meta(), store, refine=refine, request_id="req-1")
        self.assertEqual(seen, dict(upload_id=res.upload_id, request_id="req-1"))


class StubSafetyTests(unittest.TestCase):
    def test_stub_result_is_marked_stub_and_never_stored(self):
        """가짜 결과 클래스에 칸이 더해져도 model='stub'이 유지되어 DB에 저장되지 않는다 (칸 순서가 바뀐 적이 있어 고정)."""
        out = stub_refine([ComplaintInput("C1", "일반 민원", "t", "b", None)])[0]
        self.assertEqual((out.model, out.class_method), ("stub", None))
        store = MemoryStore(GRID)
        run_load(xlsx([general(1)]), FILE, meta(), store, refine=stub_refine)
        row = next(iter(store.complaints.values()))
        self.assertEqual([row[c] for c in port.AI_COLS], [None] * 5)
        self.assertIsNone(row["class_method"])
