"""C-10 재발 표시 시험."""
import unittest

from app.services.load.pipeline import run_load
from app.services.load.recurrence import mark_recurrence
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import GRID, meta, spp, xlsx

FILE = "민원 상세정보 현황-20261022190720.xlsx"


def rec(cid, gid="G1", typ="불법 주정차", received="2025-11-10", processed=None):
    return dict(complaint_id=cid, gid=gid, report_type_raw=typ, received_date=received, processed_date=processed)


class MarkTests(unittest.TestCase):
    def test_flag_after_processed_prior_in_same_file(self):
        rs = [rec("A", received="2025-11-01", processed="2025-11-03"), rec("B", received="2025-11-10")]
        self.assertEqual(mark_recurrence(rs, []), 1)
        self.assertEqual((rs[0]["recurrence_flag"], rs[1]["recurrence_flag"], rs[1]["recurrence_prev_id"]), (None, "재발 1회", "A"))

    def test_prior_must_be_processed_before_received(self):
        rs = [rec("A", received="2025-11-01", processed="2025-11-05"), rec("B", received="2025-11-05"),
              rec("C", received="2025-11-02")]
        mark_recurrence(rs, [])
        self.assertEqual([r["recurrence_flag"] for r in rs], [None, None, None])     # 처리일 5일 전/당일 접수는 재발 아님

    def test_prior_without_processed_date_is_ignored(self):
        rs = [rec("A", received="2025-11-01"), rec("B", received="2025-11-10")]
        mark_recurrence(rs, [])
        self.assertIsNone(rs[1]["recurrence_flag"])

    def test_same_place_and_type_only(self):
        rs = [rec("A", processed="2025-11-01", received="2025-10-30"), rec("B", gid="G2"), rec("C", typ="다른 유형"),
              rec("D", gid=None), rec("E", typ=None)]
        mark_recurrence(rs, [])
        self.assertEqual([r["recurrence_flag"] for r in rs], [None] * 5)

    def test_counts_and_latest_prior_from_db(self):
        priors = [dict(complaint_id="P1", gid="G1", report_type_raw="불법 주정차", processed_date="2024-01-02"),
                  dict(complaint_id="P2", gid="G1", report_type_raw="불법 주정차", processed_date="2025-03-04"),
                  dict(complaint_id="B", gid="G1", report_type_raw="불법 주정차", processed_date="2025-12-31")]  # 같은 ID는 새 값을 씀
        rs = [rec("B")]
        mark_recurrence(rs, priors)
        self.assertEqual((rs[0]["recurrence_flag"], rs[0]["recurrence_prev_id"]), ("재발 2회", "P2"))


class PipelineRecurrenceTests(unittest.TestCase):
    def rows(self):
        a = list(spp(1, received="2025-11-01", processed="2025-11-03"))
        b = list(spp(2, received="2025-11-10", processed="-"))
        return [tuple(a), tuple(b)]

    def test_stored_with_change_log_on_rerun(self):
        st = MemoryStore(GRID)
        res = run_load(xlsx(self.rows()), FILE, meta(), st)
        by = {c["source_receipt_no"]: c for c in st.complaints.values()}
        self.assertIsNone(by["SPP-2511-ABC0001"]["recurrence_flag"])
        self.assertEqual(by["SPP-2511-ABC0002"]["recurrence_flag"], "재발 1회")
        self.assertEqual(by["SPP-2511-ABC0002"]["recurrence_prev_id"], by["SPP-2511-ABC0001"]["complaint_id"])
        self.assertTrue(res.remark.endswith("재발 1"))
        again = run_load(xlsx(self.rows()), FILE, meta(), st)
        self.assertEqual((again.counts.existing, again.counts.updated), (2, 0))

    def test_skipped_when_columns_missing(self):
        st = MemoryStore(GRID, recurrence=False)
        res = run_load(xlsx(self.rows()), FILE, meta(), st)
        self.assertTrue(any("재발 표시 칸이 없어" in w for w in res.warnings))
        self.assertNotIn("recurrence_flag", next(iter(st.complaints.values())))

    def test_later_load_marks_via_db_history(self):
        st = MemoryStore(GRID)
        run_load(xlsx([self.rows()[0]]), FILE, meta(), st)
        nov = meta(period_start=meta().period_start, period_end=meta().period_end)
        run_load(xlsx([self.rows()[1]]), FILE, nov, st)
        by = {c["source_receipt_no"]: c for c in st.complaints.values()}
        self.assertEqual(by["SPP-2511-ABC0002"]["recurrence_flag"], "재발 1회")


class KindAndRecomputeTests(unittest.TestCase):
    def test_ped_type_is_preferred_over_report_type(self):
        rs = [dict(rec("A", received="2025-11-01", processed="2025-11-03"), ped_type="불법주정차"),
              dict(rec("B", typ="다른 신고분류"), ped_type="불법주정차")]
        mark_recurrence(rs, [])
        self.assertEqual(rs[1]["recurrence_flag"], "재발 1회")             # 신고 분류가 달라도 보행_유형이 같으면 같은 유형

    def test_recompute_updates_and_logs_changes(self):
        from app.services.load.recurrence import recompute_recurrence
        st = MemoryStore(GRID)
        run_load(xlsx([spp(2, received="2025-11-10", processed="-")]), FILE, meta(), st)       # 늦은 달을 먼저 올림
        run_load(xlsx([spp(1, received="2025-11-01", processed="2025-11-03")]), FILE, meta(), st)
        late = next(c for c in st.complaints.values() if c["source_receipt_no"] == "SPP-2511-ABC0002")
        self.assertIsNone(late["recurrence_flag"])                                              # 늦은 민원을 먼저 올려 놓침
        marked, touched = recompute_recurrence(st, "재발 다시 계산 2026-10-22")
        self.assertEqual((marked, touched), (1, 1))
        self.assertEqual(late["recurrence_flag"], "재발 1회")
        self.assertEqual(st.changes, [])                                                        # 처음 채운 것은 80에 남기지 않음
        self.assertEqual(recompute_recurrence(st, "x"), (1, 0))                                 # 두 번째는 바뀐 것 없음
        extra = spp(3, received="2025-11-02", processed="2025-11-04")
        run_load(xlsx([extra]), FILE, meta(), st)
        marked, touched = recompute_recurrence(st, "재발 다시 계산")
        self.assertEqual(late["recurrence_flag"], "재발 2회")                                   # 값이 바뀐 것은 남김
        self.assertEqual(sorted(c["changed_column"] for c in st.changes)[:1], ["recurrence_flag"])


class ForeignKeyOrderTests(unittest.TestCase):
    """실제 MySQL 시험에서 나온 문제: 재발 표시가 같은 파일의 나중에 들어갈 민원을 가리키면 외래키 오류."""

    def test_prev_id_pointing_to_later_row_in_same_file(self):
        st = MemoryStore(GRID)
        late_first = [spp(2, received="2025-11-10", processed="-"), spp(1, received="2025-11-01", processed="2025-11-03")]
        run_load(xlsx(late_first), FILE, meta(), st)                    # 파일 순서는 늦은 민원이 먼저
        by = {c["source_receipt_no"]: c for c in st.complaints.values()}
        self.assertEqual(by["SPP-2511-ABC0002"]["recurrence_prev_id"], by["SPP-2511-ABC0001"]["complaint_id"])

    def test_existing_row_can_point_to_new_row(self):
        st = MemoryStore(GRID)
        run_load(xlsx([spp(2, received="2025-11-10", processed="-")]), FILE, meta(), st)
        run_load(xlsx([spp(2, received="2025-11-10", processed="-"), spp(1, received="2025-11-01", processed="2025-11-03")]),
                 FILE, meta(), st)
        by = {c["source_receipt_no"]: c for c in st.complaints.values()}
        self.assertEqual(by["SPP-2511-ABC0002"]["recurrence_prev_id"], by["SPP-2511-ABC0001"]["complaint_id"])
