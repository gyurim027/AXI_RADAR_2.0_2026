"""C-08 연계 시험: 관련 여부 판단 방법(79 class_method) 저장 · 사람 수정값 보호."""
from types import SimpleNamespace

from app.services.load.ai01_stub import Ai01Result
from app.services.load.pipeline import run_load
from app.services.load.store import MemoryStore
from tests.test_load_fixtures import BaseLoadCase, GRID, general, meta, spp, xlsx

FILE = "민원 상세정보 현황-20261022190720.xlsx"


def res(item, method="규칙", relevance="보행안전 관련", conf=1.0, summary="요약", status="ok", model="mask-1+sum-2+cls-2"):
    return Ai01Result(item.complaint_id, status, summary, relevance, None, conf, "근거", method, model)


def by_pos(store):
    return {c["raw_position"].rsplit(" ", 1)[1]: c for c in store.complaints.values()}          # 원본 번호 → 행


class MethodTests(BaseLoadCase):
    def setUp(self):
        super().setUp()
        self.store = MemoryStore(GRID)

    def load(self, refine, rows=None, **kw):
        return run_load(xlsx(rows or [spp(1), general(2)]), FILE, meta(), self.store, refine=refine, **kw)

    def test_rule_and_ai_methods_are_stored(self):
        def refine(items, **_):
            return [res(items[0], "규칙"), res(items[1], "AI", conf=1.0)]       # 모델이 신뢰도 1.0을 내도 방법은 AI
        self.load(refine)
        rows = by_pos(self.store)
        self.assertEqual((rows["1"]["class_method"], rows["2"]["class_method"]), ("규칙", "AI"))
        self.assertEqual(rows["2"]["class_confidence"], 1.0)

    def test_unknown_relevance_still_gets_its_real_method(self):
        self.load(lambda items, **_: [res(i, "AI", relevance="불명", conf=0.3) for i in items])
        self.assertEqual({c["class_method"] for c in self.store.complaints.values()}, {"AI"})
        self.assertEqual({c["relevance"] for c in self.store.complaints.values()}, {"불명"})

    def test_failures_and_stub_leave_method_empty(self):
        def refine(items, **_):
            return [Ai01Result(items[0].complaint_id, "mask_failed", model="m"), Ai01Result(items[1].complaint_id, "error", model="m")]
        self.load(refine)
        self.assertEqual({c["class_method"] for c in self.store.complaints.values()}, {None})
        store2 = MemoryStore(GRID)
        run_load(xlsx([spp(1)]), FILE, meta(), store2)                                   # 가짜 함수
        self.assertIsNone(next(iter(store2.complaints.values()))["class_method"])

    def test_bad_values_and_old_ai01_are_ignored(self):
        def refine(items, **_):
            return [res(items[0], "사람"), SimpleNamespace(complaint_id=items[1].complaint_id, status="ok", model="m",    # class_method가 없는 옛 AI-01
                                                           masked_summary="요약", relevance="비관련", ped_type=None,
                                                           class_confidence=0.9, class_reason="근거")]
        self.load(refine)
        self.assertEqual({c["class_method"] for c in self.store.complaints.values()}, {None})       # 적재는 사람 값을 쓰지 않음
        self.assertEqual(by_pos(self.store)["2"]["relevance"], "비관련")

    def test_pii_in_summary_clears_method_too(self):
        self.load(lambda items, **_: [res(items[0], summary="전화 010-1234-5678"), res(items[1])])
        rows = by_pos(self.store)
        self.assertEqual((rows["1"]["class_method"], rows["1"]["class_reason"]), (None, "가림 실패"))
        self.assertEqual(rows["2"]["class_method"], "규칙")

    def test_first_fill_is_silent_and_later_change_is_logged(self):
        self.load(lambda items, **_: [Ai01Result(i.complaint_id, "error", model="m") for i in items])    # 먼저 AI 칸이 빈 채 들어감
        self.load(lambda items, **_: [res(i, "규칙") for i in items])                                    # 처음 채움
        self.assertEqual(self.store.changes, [])
        self.load(lambda items, **_: [res(i, "AI", conf=0.8) for i in items], rerun_ai01=True)           # 다시 돌려 방법이 바뀜
        cols = sorted({c["changed_column"] for c in self.store.changes})
        self.assertIn("class_method", cols)
        self.assertTrue(all(c["load_batch"].startswith("AI-01 ") for c in self.store.changes))

    def test_failed_rerun_does_not_wipe_method(self):
        self.load(lambda items, **_: [res(i, "규칙") for i in items])
        self.load(lambda items, **_: [Ai01Result(i.complaint_id, "error", model="m") for i in items], rerun_ai01=True)
        self.assertEqual({c["class_method"] for c in self.store.complaints.values()}, {"규칙"})

    def test_column_missing_is_skipped_with_warning(self):
        store = MemoryStore(GRID, class_method=False)
        r = run_load(xlsx([spp(1)]), FILE, meta(), store, refine=lambda items, **_: [res(i) for i in items])
        self.assertNotIn("class_method", next(iter(store.complaints.values())))
        self.assertTrue(any("class_method" in w for w in r.warnings))


class HumanEditTests(BaseLoadCase):
    """C-08이 사람이 고친 관련 여부(class_method=사람)는 AI-01 재실행·재업로드가 덮어쓰지 않는다."""

    def setUp(self):
        super().setUp()
        self.store = MemoryStore(GRID)
        run_load(xlsx([spp(1), general(2)]), FILE, meta(), self.store,
                 refine=lambda items, **_: [res(i, "AI", relevance="보행안전 관련", conf=0.7) for i in items])
        self.row = by_pos(self.store)["1"]
        self.row.update(relevance="비관련", class_method="사람", class_confidence=None, class_reason="운영자 검수")   # C-08이 고침
        self.store.commit()
        self.sent = []

    def refine(self, items, **_):
        self.sent.append([i.complaint_id for i in items])
        return [res(i, "규칙", relevance="보행안전 관련", conf=1.0, summary="새 요약") for i in items]

    def test_rerun_skips_and_keeps_human_values(self):
        run_load(xlsx([spp(1), general(2)]), FILE, meta(), self.store, refine=self.refine, rerun_ai01=True)
        rows = by_pos(self.store)
        self.assertEqual([rows["1"][c] for c in ("relevance", "class_method", "class_confidence", "class_reason")],
                         ["비관련", "사람", None, "운영자 검수"])
        self.assertEqual(self.sent, [[rows["2"]["complaint_id"]]])               # 사람이 고친 민원은 AI-01에 보내지도 않음
        self.assertEqual(rows["2"]["masked_summary"], "새 요약")                  # 다른 민원은 평소처럼 갱신
        self.assertFalse(any(c["complaint_id"] == rows["1"]["complaint_id"] for c in self.store.changes))

    def test_plain_reupload_keeps_human_values(self):
        run_load(xlsx([spp(1), general(2)]), FILE, meta(), self.store, refine=self.refine)
        self.assertEqual((self.row["relevance"], self.row["class_method"]), ("비관련", "사람"))
        self.assertEqual(self.sent, [])

    def test_defensive_diff_never_overwrites_human_value(self):
        from app.services.load.upsert import diff_record
        new = dict(self.row, relevance="보행안전 관련", class_method="AI", class_reason="다른 근거")
        changes, silent = diff_record(new, self.row)
        self.assertFalse({"relevance", "class_method", "class_reason"} & (set(changes) | set(silent)))
