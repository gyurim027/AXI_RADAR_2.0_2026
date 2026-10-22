"""적재 흐름 시험: 가짜 DB(MemoryStore)로 신규 · 기존 · 갱신 · 되돌림 · 원문 미저장 · AI-01 자리."""
import datetime as dt
import logging
import unittest

from app.services.load.ai01_stub import Ai01Result
from app.services.load.pipeline import UploadMeta, run_load, validate_meta
from app.services.load.reader import LoadFileError
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import BaseLoadCase, GRID, general, meta, spp, xlsx

FILE = "민원 상세정보 현황-20261022190720.xlsx"


def rows_basic():
    return [spp(1), spp(2, processed="-"), general(3), general(4, title="같은 제목", body="같은 본문")]


class PipelineTests(BaseLoadCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryStore(GRID)

    def load(self, rows, **kw):
        return run_load(xlsx(rows), FILE, meta(), self.store, **kw)

    def test_new_then_existing(self):
        a = self.load(rows_basic())
        self.assertEqual((a.counts.new, a.counts.existing, a.counts.updated), (4, 0, 0))
        b = self.load(rows_basic())
        self.assertEqual((b.counts.new, b.counts.existing, b.counts.updated), (0, 4, 0))
        self.assertEqual(self.store.changes, [])
        self.assertEqual(len(self.store.complaints), 4)

    def test_84_upload_rows(self):
        res = self.load(rows_basic())
        up = self.store.uploads[res.upload_id]
        self.assertEqual((up["file_name"], up["check_result"], up["row_cnt"]), (FILE, "통과", 4))
        self.assertIsNone(up["uploaded_by"])
        self.assertTrue(up["remark"].startswith("신규 4 · 기존 0 · 갱신 0"))
        ids = {c["upload_id"] for c in self.store.complaints.values()}
        self.assertEqual(ids, {res.upload_id})

    def test_processed_date_change_writes_three_change_rows(self):
        self.load(rows_basic())
        again = rows_basic()
        again[1] = spp(2, processed="2025-11-10")                 # 처리일이 새로 생김
        res = self.load(again)
        self.assertEqual((res.counts.updated, res.counts.change_rows), (1, 3))
        cols = sorted(c["changed_column"] for c in self.store.changes)
        self.assertEqual(cols, ["has_processed_date", "processed_date", "processing_days"])
        pd = next(c for c in self.store.changes if c["changed_column"] == "processed_date")
        self.assertEqual((pd["old_value"], pd["new_value"]), (None, "2025-11-10"))
        self.assertEqual(pd["load_batch"], f"{res.upload_id} {FILE}")
        self.assertEqual((pd["changed_by_type"], pd["changed_by_user"]), ("적재", None))
        row = next(c for c in self.store.complaints.values() if c["source_receipt_no"] == "SPP-2511-ABC0002")
        self.assertEqual(row["processed_date"], "2025-11-10")
        self.assertEqual(row["touched"], 1)                        # db_last_updated_at 갱신
        self.assertEqual(row["upload_id"], 1)                      # 처음 들어온 업로드 번호는 그대로

    def test_missing_rows_are_kept_and_counted(self):
        self.load(rows_basic())
        res = self.load(rows_basic()[:2])
        self.assertEqual(res.counts.missing, 2)
        self.assertEqual(len(self.store.complaints), 4)

    def test_address_converted_coords_are_not_wiped(self):
        self.load(rows_basic())
        rec = next(c for c in self.store.complaints.values() if c["source_receipt_no"] == "SPP-2511-ABC0001")
        loc = rec["location_text"]
        rec.update(lat=None, lon=None, gid=None, coord_method="주소 변환(지번 주소)", coord_accuracy="보통")
        again = rows_basic()
        # 위치 글자는 같고 이번 파일에는 본문 좌표가 없음 → 변환된 값을 지우지 않는다
        again[0] = spp(1, pos="")
        res = self.load(again)
        self.assertEqual(rec["coord_method"], "주소 변환(지번 주소)")
        self.assertEqual(rec["location_text"], loc)
        self.assertEqual(res.counts.updated, 0)

    def test_failure_rolls_back_and_keeps_84_line(self):
        self.load(rows_basic())
        again = rows_basic()
        again[1] = spp(2, processed="2025-11-10")
        broken = MemoryStore(GRID, fail_on_change_insert=True)
        broken.complaints = {k: dict(v) for k, v in self.store.complaints.items()}
        broken.commit()
        with self.assertRaises(RuntimeError):
            run_load(xlsx(again), FILE, meta(), broken)
        row = next(c for c in broken.complaints.values() if c["source_receipt_no"] == "SPP-2511-ABC0002")
        self.assertIsNone(row["processed_date"])                   # 되돌려짐
        self.assertEqual(broken.changes, [])
        up = broken.uploads[max(broken.uploads)]
        self.assertTrue(up["check_result"].startswith("실패"))
        self.assertNotIn("시험용", up["check_result"])             # 예외 상세는 남기지 않음

    def test_rejects_bad_file_and_logs_failure(self):
        with self.assertRaises(LoadFileError):
            run_load(xlsx([], header=("가", "나", "다", "라", "마", "바")), FILE, meta(), self.store)
        up = self.store.uploads[1]
        self.assertTrue(up["check_result"].startswith("실패 (칸 이름"))
        self.assertEqual(self.store.complaints, {})

    def test_rejects_dates_outside_period(self):
        with self.assertRaises(LoadFileError) as cm:
            self.load([spp(1), general(2, received="2025-12-01")])
        self.assertEqual(cm.exception.code, "period_mismatch")
        self.assertEqual(self.store.complaints, {})

    def test_check_fails_when_processed_before_received(self):
        with self.assertRaises(LoadFileError) as cm:
            self.load([spp(1, processed="2025-11-01")])
        self.assertEqual(cm.exception.code, "check_failed")
        self.assertIn("처리일이 접수일보다 빠른", cm.exception.message)

    def test_check_fails_when_receipt_owned_by_other_id(self):
        self.load([spp(1)])
        other = next(iter(self.store.complaints.values()))
        other["complaint_id"] = "Cother0000000"
        self.store.complaints = {"Cother0000000": other}
        with self.assertRaises(LoadFileError) as cm:
            self.load([spp(1)])
        self.assertEqual(cm.exception.code, "check_failed")

    def test_meta_rules(self):
        for bad in (meta(source=" "), meta(period_start=dt.date(2025, 11, 2)), meta(period_end=dt.date(2025, 12, 31))):
            with self.assertRaises(LoadFileError):
                validate_meta(bad)
        validate_meta(meta())


class Ai01Tests(BaseLoadCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryStore(GRID)

    def test_stub_is_called_but_not_stored(self):
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store)
        self.assertEqual(res.ai.stub, 4)
        for c in self.store.complaints.values():
            self.assertIsNone(c["masked_summary"])
            self.assertIsNone(c["relevance"])

    def test_real_result_is_stored_and_rerun_logs_ai_change(self):
        def fake(model, summary):
            def refine(items):
                return [Ai01Result(i.complaint_id, "ok", summary, "보행안전 관련", None, 0.9, "근거", model) for i in items]
            return refine
        run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=fake("mask v0.9", "요약1"))
        self.assertTrue(all(c["masked_summary"] == "요약1" for c in self.store.complaints.values()))
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=fake("mask v0.9", "요약2"), rerun_ai01=True)
        self.assertEqual(res.counts.updated, 4)
        ai_rows = [c for c in self.store.changes if c["changed_column"] == "masked_summary"]
        self.assertEqual(len(ai_rows), 4)
        self.assertTrue(ai_rows[0]["load_batch"].startswith("AI-01 "))

    def test_ai01_not_called_again_for_rows_that_already_have_results(self):
        calls = []

        def refine(items):
            calls.append(len(items))
            return [Ai01Result(i.complaint_id, "ok", "요약", "보행안전 관련", None, 0.9, "근거", "mask v0.9") for i in items]
        run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=refine)
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=refine)
        self.assertEqual(calls, [4])                                   # 두 번째에는 보낼 민원이 없어 부르지 않음
        self.assertEqual((res.counts.existing, res.counts.updated), (4, 0))
        self.assertEqual(self.store.changes, [])

    def test_first_fill_of_existing_rows_is_not_logged_in_80(self):
        run_load(xlsx(rows_basic()), FILE, meta(), self.store)         # AI-01 칸은 비어 있음 (가짜 함수 결과는 안 씀)
        real = lambda items: [Ai01Result(i.complaint_id, "ok", "요약", "관련", None, 0.9, "근거", "mask v0.9") for i in items]
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=real)
        self.assertEqual(res.counts.updated, 0)
        self.assertEqual(self.store.changes, [])
        self.assertTrue(all(c["masked_summary"] == "요약" for c in self.store.complaints.values()))

    def test_failed_rerun_does_not_wipe_existing_values(self):
        ok = lambda items: [Ai01Result(i.complaint_id, "ok", "요약", "관련", None, 0.9, "근거", "m") for i in items]
        run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=ok)

        def fail(items):
            raise RuntimeError("꺼짐")
        run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=fail, rerun_ai01=True)
        self.assertTrue(all(c["masked_summary"] == "요약" for c in self.store.complaints.values()))

    def test_mask_failed_and_error_do_not_stop_load(self):
        def refine(items):
            out = []
            for k, i in enumerate(items):
                st = ["ok", "mask_failed", "error", "ok"][k % 4]
                out.append(Ai01Result(i.complaint_id, st, "요약" if st == "ok" else None, None, None, None, None, "m"))
            return out
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=refine)
        self.assertEqual((res.ai.ok, res.ai.mask_failed, res.ai.error), (2, 1, 1))
        self.assertEqual(len(self.store.complaints), 4)

    def test_ai_exception_leaves_ai_columns_empty_and_continues(self):
        def boom(items):
            raise RuntimeError("모델 꺼짐")
        res = run_load(xlsx(rows_basic()), FILE, meta(), self.store, refine=boom)
        self.assertEqual(res.ai.error, 4)
        self.assertEqual(res.counts.new, 4)


class NoRawTextTests(BaseLoadCase):
    def test_raw_text_never_reaches_store_logs_or_messages(self):
        marker_t, marker_b = "원문제목ZQX", "원문본문ZQX"
        rows = [general(1, title=marker_t, body=marker_b + " 010-9999-8888"), spp(2)]
        store = MemoryStore(GRID)
        with self.assertLogs("radar.load", level="DEBUG") as logs:
            logging.getLogger("radar.load").info("start")
            res = run_load(xlsx(rows), FILE, meta(), store)
        dump = repr(store.complaints) + repr(store.changes) + repr(store.uploads) + repr(res) + "\n".join(logs.output)
        self.assertNotIn("ZQX", dump)
        self.assertNotIn("9999-8888", dump)
        self.assertEqual(next(iter(store.complaints.values()))["raw_pii_patterns"], "휴대전화")


class CoordGuardTests(BaseLoadCase):
    def test_ai03_filled_coords_survive_reupload(self):
        st = MemoryStore(GRID)
        run_load(xlsx([spp(1, pos=""), general(2)]), FILE, meta(), st)
        rec = next(c for c in st.complaints.values() if c["source_receipt_no"] == "SPP-2511-ABC0001")
        rec.update(lat=37.371498, lon=127.027058, gid="G1", coord_method="본문 장소 표현으로 찾은 위치(AI-03)", coord_accuracy="낮음")
        res = run_load(xlsx([spp(1, pos=""), general(2)]), FILE, meta(), st)
        self.assertEqual((rec["gid"], rec["coord_method"]), ("G1", "본문 장소 표현으로 찾은 위치(AI-03)"))
        self.assertEqual(res.counts.updated, 0)
