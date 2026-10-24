"""AI-01 민원 정제 시험. 가짜 문장만 쓰고, 이름 모델과 LLM은 가짜로 바꿔 돈다 (torch·Ollama 없이).
실행: uv run python -m pytest tests/test_ai01_refine.py"""
import collections
import unittest
from unittest import mock

from app.core.llm import LlmResult
from app.services.ai01 import classify as cls
from app.services.ai01 import judge as jdg
from app.services.ai01 import masking, refine
from app.services.ai01 import summarize as summ


def fake_ner(names=("홍길동",)):
    """지정한 낱말을 이름으로 돌려주는 가짜 이름 모델."""
    def ner(seg):
        out = []
        for n in names:
            i = seg.find(n)
            if i >= 0:
                out.append({"entity_group": "NAME", "score": 0.9, "start": i, "end": i + len(n), "word": n})
        return out
    return ner


def llm(data):
    return LlmResult(ok=True, task="t", route="internal", model="m", data=data)


class MaskingTests(unittest.TestCase):
    def mask(self, text, names=()):
        with mock.patch.object(masking, "common_words", return_value=frozenset({"허송"})):
            return masking.mask("제목", text, ner=fake_ner(names))

    def test_rules_hide_pii_and_keep_places(self):
        r = self.mask("판교로256번길 25 앞. 연락처 031 729 1234, 010-1234-5678. 차량 12가3456, 경기(아)1647, "
                      "신청번호 1AA-2101-0123456, 102동 1203호, (2006년 06월 14일생)")
        self.assertTrue(r.ok)
        for leak in ("729 1234", "1234-5678", "12가3456", "1647", "0123456", "1203호", "2006년"):
            self.assertNotIn(leak, r.text)
        self.assertIn("판교로256번길 25", r.text)
        self.assertFalse(r.location_lost)

    def test_model_names_and_common_words(self):
        r = self.mask("담당자 홍길동 씨가 10일을 허송세월하고 있습니다", names=("홍길동", "허송"))
        self.assertIn("[이름] 씨", r.text)
        self.assertIn("허송세월", r.text)                     # 흔한 낱말이라 가리지 않음

    def test_place_name_after_label_is_kept(self):
        r = self.mask("정류장 이름 : 도촌초교. 이름: 김철수, 이영희")
        self.assertIn("도촌초교", r.text)
        self.assertNotIn("김철수", r.text)
        self.assertNotIn("이영희", r.text)

    def test_preprocess_drops_tag_and_coordinate_lines(self):
        t = masking.preprocess("제목", "[민원 유입 경로] 모바일\n본문입니다\n위도 : 37.1 경도 : 127.1\n(1/2) C : 2023/05/06 12:30:00\n"
                                       "* 안전신문고 신고파일(사진) 촬영시간 및 경로 안내 *\n*\n* (1/2) S: 2021/05/31 17:14:03\n차량번호 : *\n* G:휴대폰(안전신문고 앱)")
        self.assertEqual(t, "제목\n본문입니다")


class BatchTemplateTests(unittest.TestCase):
    def test_repeated_lines_are_dropped(self):
        bodies = ["안내 문구 한 줄\n본문 %d" % i for i in range(30)]
        drop = masking.repeated_lines(bodies)
        self.assertEqual(drop, frozenset({"안내 문구 한 줄"}))
        self.assertEqual(masking.preprocess("제목", bodies[0], drop), "제목\n본문 0")
        self.assertEqual(masking.repeated_lines(bodies[:5]), frozenset())     # 너무 적으면 찾지 않음

    def test_only_spp_lines_are_dropped(self):
        same = "우리 단지 앞 인도에 매일 차가 올라와 있습니다"            # 집단 민원: 같은 글을 여러 번 올림
        items = [refine.ComplaintInput("C%012d" % i, "일반 민원", "제목", same) for i in range(30)]
        seen = []
        orig = masking.mask
        def spy(title, body, ner=None, drop=frozenset()):
            seen.append(drop)
            return orig(title, body, ner=ner, drop=drop)
        with mock.patch.object(masking, "mask", side_effect=spy), \
             mock.patch.object(masking, "common_words", return_value=frozenset()), \
             mock.patch.object(summ, "call_llm", return_value=llm({"summary": "인도 주차"})), \
             mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 0.9, "reason": "보행 공간: 인도"})):
            refine.refine_complaints(items, ner=fake_ner(()))
        self.assertTrue(all(d == frozenset() for d in seen))

    def test_spp_fixed_template_lines(self):
        self.assertIn("횡단보도 불법 주정차 신고입니다.", masking.spp_template_lines())


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        cls.type_rules.cache_clear()

    def test_type_default_by_keyword(self):
        self.assertEqual(cls.type_default("횡단보도 불법주정차"), cls.RELATED)
        self.assertEqual(cls.type_default("수진동성당 앞 교차로 모퉁이 불법 주정차"), cls.RELATED)
        self.assertEqual(cls.type_default("장애인 전용구역 횡단보도"), cls.UNRELATED)   # 비관련 낱말을 먼저
        self.assertEqual(cls.type_default("기타 불법 주정차"), cls.UNKNOWN)
        self.assertIsNone(cls.type_default(None))

    def test_body_confirms_or_sends_to_ai(self):
        self.assertEqual(cls.by_type("횡단보도 불법 주정차", "횡단보도 위 주차")[0], cls.RELATED)
        self.assertIsNone(cls.by_type("횡단보도 불법 주정차", "아파트 주차장 내 충전 구역"))         # 어긋남 → AI
        self.assertEqual(cls.by_type("소화전 불법 주정차", "소화전 앞 주차")[0], cls.UNRELATED)
        self.assertIsNone(cls.by_type("소화전 불법 주정차", "소화전 앞 차 때문에 인도를 못 지나갑니다"))  # 보행 언급 → AI

    def test_unknown_type_stays_unknown_unless_asked(self):
        self.assertEqual(cls.classify("불법 주정차 신고", "기타 불법 주정차")[0], cls.UNKNOWN)
        with mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 0.9,
                                                                   "reason": "보행 공간 불법 주정차: 인도 통행 방해"})):
            self.assertEqual(cls.classify("불법주정차구역에 인도 통행 방해", "기타 불법 주정차")[0], cls.RELATED)
        with mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 0.8,
                                                                   "reason": "보행 공간 불법 주정차: 인도"})):
            self.assertEqual(cls.classify("인도에 주차", "기타 불법 주정차", unknown_to_ai=True)[0], cls.RELATED)

    def test_rules_before_model(self):
        self.assertEqual(cls.by_rule("공영주차장 내 충전 구역에 일반 차 주차")[0], cls.UNRELATED)
        self.assertEqual(cls.by_rule("불법 주정차 때문에 중앙분리대 설치 요청")[0], cls.RELATED)
        self.assertIsNone(cls.by_rule("보도블록이 깨졌습니다"))

    def test_model_answer_is_normalized(self):
        with mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 1.7,
                                                                   "reason": "보행 공간 파손: 보도블록\n둘째 줄"})):
            self.assertEqual(cls.by_model("보도블록이 깨졌습니다"), (cls.RELATED, 1.0, "보행 공간 파손: 보도블록"))

    def test_method_follows_decision_path(self):
        self.assertEqual(cls.classify("불법 주정차 신고", "기타 불법 주정차")[3], cls.BY_RULE)            # 규칙이 낸 불명
        self.assertEqual(cls.classify("공영주차장 내 충전 구역에 일반 차 주차")[3], cls.BY_RULE)
        with mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 1.0,
                                                                   "reason": "보행 공간 파손: 보도블록"})):
            self.assertEqual(cls.classify("보도블록이 깨졌습니다")[2:], ("보행 공간 파손: 보도블록", cls.BY_AI))  # 1.0이어도 AI
        with mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "불명", "confidence": 0.4,
                                                                   "reason": "불명: 장소 없음"})):
            self.assertEqual(cls.classify("확인 부탁드립니다")[::3], (cls.UNKNOWN, cls.BY_AI))             # 모델이 낸 불명
        with mock.patch.object(cls, "call_llm", return_value=LlmResult(ok=False, task="t", error_code="timeout")):
            self.assertIsNone(cls.classify("보도블록이 깨졌습니다"))


class RefineTests(unittest.TestCase):
    def run_one(self, body="긴 글 " * 60, summary="○○로 인도에 차가 주차되어 보행자가 차도로 걷습니다.", answer=None):
        return self.run_many([body], summary, answer)[0][0]

    def run_many(self, bodies, summary="○○로 인도에 차가 주차되어 보행자가 차도로 걷습니다.", answer=None):
        """한 번에 받기(ONE_CALL=True)로 돌린다. 돌려준 값: (결과 목록, judge 호출 수)."""
        answer = answer or {"relevance": "관련", "confidence": 0.9, "reason": "보행 공간 불법 주정차: 인도 주차"}
        items = [refine.ComplaintInput(f"C00000000000{i}", "일반 민원", "제목", b) for i, b in enumerate(bodies)]
        with mock.patch.object(refine, "ONE_CALL", True), \
             mock.patch.object(masking, "common_words", return_value=frozenset()), \
             mock.patch.object(jdg, "call_llm", return_value=llm({"summary": summary, **answer})) as j, \
             mock.patch.object(summ, "call_llm") as s, mock.patch.object(cls, "call_llm") as c:
            out = refine.refine_complaints(items, ner=fake_ner(()))
        s.assert_not_called()                                 # 긴 글은 요약·분류를 따로 부르지 않는다
        c.assert_not_called()
        return out, j.call_count

    def test_ok_fills_five_columns(self):
        r = self.run_one("○○로 인도에 매일 차가 주차합니다. " * 20)
        self.assertEqual((r.status, r.relevance, r.class_confidence, r.class_method), ("ok", cls.RELATED, 0.9, cls.BY_AI))
        self.assertIsNone(r.ped_type)
        self.assertTrue(r.masked_summary and r.class_reason)

    def test_summary_is_checked_again(self):
        r = self.run_one("○○로 인도 주차. " * 30, summary="○○로 인도에 12가3456 차량이 주차합니다.")
        self.assertNotIn("12가3456", r.masked_summary)
        self.assertNotIn("[", r.masked_summary)

    def test_short_text_skips_model(self):
        with mock.patch.object(summ, "call_llm") as c:
            out, hits = summ.summarize("횡단보도 위 [차량번호] 주차")
        c.assert_not_called()
        self.assertEqual((out, hits), ("횡단보도 위 주차", []))

    def test_particle_ro_is_not_made_up_place(self):
        text = "○○초등학교 앞 인도에 차가 매일 주차합니다. 단속과 볼라드 설치를 원합니다."
        self.assertEqual(summ.made_up_places("인도로 차가 올라와 볼라드 설치로 막아 달라는 요청", text), [])
        self.assertEqual(summ.made_up_places("성남시 ○○초등학교 앞 인도 주차", text), [])
        self.assertEqual(summ.made_up_places("분당구 정자동 교차로에 주차", text), ["분당구", "정자동"])      # 지어낸 장소는 그대로 잡는다

    def test_made_up_place_falls_back(self):
        long = "○○로 인도에 차가 매일 주차합니다. " * 20
        with mock.patch.object(summ, "call_llm", return_value=llm({"summary": "분당구 정자동 교차로에 주차"})):
            out, hits = summ.summarize(long)
        self.assertEqual(hits, ["지어낸 장소"])
        self.assertNotIn("정자동", out)

    def test_report_type_agrees_skips_models(self):
        item = refine.ComplaintInput("C000000000003", "안전신문고(SPP)", "횡단보도 불법 주정차 신고입니다",
                                     "횡단보도 위에 차가 서 있습니다", "횡단보도 불법 주정차")
        with mock.patch.object(masking, "common_words", return_value=frozenset()), \
             mock.patch.object(summ, "call_llm") as s, mock.patch.object(cls, "call_llm") as c:
            r = refine.refine_complaints([item], ner=fake_ner(()))[0]
        s.assert_not_called()
        c.assert_not_called()
        self.assertEqual((r.status, r.relevance, r.class_confidence, r.class_method), ("ok", cls.RELATED, 1.0, cls.BY_RULE))
        self.assertEqual(r.masked_summary, "횡단보도 불법 주정차 · 횡단보도 위에 차가 서 있습니다")

    def test_mask_failure_is_not_classified(self):
        with mock.patch.object(masking, "left_kinds", return_value=["휴대전화"]):
            r = self.run_one("아무 글")
        self.assertEqual((r.status, r.class_reason, r.relevance, r.class_method), ("mask_failed", "가림 실패", None, None))

    def test_rule_wins_over_model_in_one_call(self):
        r = self.run_one("○○로 인도 주차. " * 30, summary="불법 주정차 때문에 중앙분리대 설치 요청",
                         answer={"relevance": "비관련", "confidence": 0.6, "reason": "차량 흐름: 정체"})
        self.assertEqual((r.relevance, r.class_confidence, r.class_method), (cls.RELATED, 1.0, cls.BY_RULE))

    def test_same_text_is_judged_once(self):
        body = "○○로 인도에 매일 차가 주차합니다. " * 20
        out, calls = self.run_many([body, body, body + "  ", "다른 글입니다. ○○동 보도블록이 깨졌습니다. " * 20])
        self.assertEqual(calls, 2)                            # 같은 글 3건(공백만 다름 포함)은 한 번
        self.assertEqual([r.complaint_id for r in out], [f"C00000000000{i}" for i in range(4)])
        self.assertEqual({r.status for r in out}, {"ok"})

    def test_default_is_two_calls(self):
        self.assertFalse(refine.ONE_CALL)                     # 한 번에 받기는 게이트 미달(2026-10-24)
        if True:
            item = refine.ComplaintInput("C000000000001", "일반 민원", "제목", "○○로 인도에 매일 차가 주차합니다. " * 20)
            with mock.patch.object(masking, "common_words", return_value=frozenset()), \
                 mock.patch.object(summ, "call_llm", return_value=llm({"summary": "○○로 인도 주차"})), \
                 mock.patch.object(cls, "call_llm", return_value=llm({"relevance": "관련", "confidence": 0.9,
                                                                       "reason": "보행 공간 불법 주정차: 인도"})), \
                 mock.patch.object(jdg, "call_llm") as j:
                r = refine.refine_complaints([item], ner=fake_ner(()))[0]
        j.assert_not_called()
        self.assertEqual((r.status, r.class_method), ("ok", cls.BY_AI))

    def test_llm_failure_is_error_without_text(self):
        item = refine.ComplaintInput("C000000000002", "일반 민원", "제목", "본문 010-1234-5678 " + "긴 글 " * 60)
        with mock.patch.object(masking, "common_words", return_value=frozenset()), \
             mock.patch.object(summ, "call_llm", return_value=LlmResult(ok=False, task="t", error_code="internal_unavailable")):
            r = refine.refine_complaints([item], ner=fake_ner(()))[0]
        self.assertEqual(r.status, "error")
        self.assertIsNone(r.masked_summary)
        self.assertIsNone(r.class_method)


if __name__ == "__main__":
    unittest.main()
