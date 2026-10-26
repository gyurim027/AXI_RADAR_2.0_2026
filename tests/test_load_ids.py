"""4장 민원ID 시험."""
import hashlib
import unittest

from app.services.load.ids import detect_source, make_ids, norm
from app.services.load.reader import RawRow


def row(n, title, body="", received="2021-01-28"):
    return RawRow(n, title, received, "-", "기타", body)


class IdTests(unittest.TestCase):
    def test_spp_id_uses_receipt_number_only(self):
        # 안전신문고는 접수번호만 재료다 (제목의 나머지 글자·번호·본문이 달라도 같은 ID). 실제 접수번호로 하는 대조는
        # scripts/load_verify.py가 로컬 원본 파일로 한다 (민원 샘플을 저장소에 올리지 않기 위해 여기서는 가짜 번호)
        want = "C" + hashlib.sha1("SPP|SPP-2101-0000001".encode()).hexdigest()[:12]
        a, _ = make_ids([row(2, "(SPP-2101-0000001) 가짜 신고 분류 신고입니다")])
        b, _ = make_ids([row(99, "(SPP-2101-0000001) 전혀 다른 글자", body="다른 본문", received="2021-02-03")])
        self.assertEqual(a, [want])
        self.assertEqual(b, [want])

    def test_source_detection(self):
        self.assertEqual(detect_source("(SPP-2101-0000001) 가"), "안전신문고(SPP)")
        self.assertEqual(detect_source("스마트국민제보 가"), "스마트국민제보")
        self.assertEqual(detect_source("그 밖"), "일반 민원")

    def test_general_uses_date_title_body_with_clean_spaces(self):
        ids, _ = make_ids([row(1, "제  목\n", "본  문 \n")])
        want = "C" + hashlib.sha1("GEN|2021-01-28|제 목|본 문".encode()).hexdigest()[:12]
        self.assertEqual(ids, [want])

    def test_smart_uses_report_date_place_title(self):
        body = "신고일자 : 2021-01-02\n위반장소: 가짜 장소"
        ids, _ = make_ids([row(1, "스마트국민제보 가짜", body)])
        want = "C" + hashlib.sha1("SMT|2021-01-02|가짜 장소|스마트국민제보 가짜".encode()).hexdigest()[:12]
        self.assertEqual(ids, [want])

    def test_same_material_gets_order_suffix(self):
        ids, numbered = make_ids([row(1, "같은", "본문"), row(2, "같은", "본문"), row(3, "다른", "본문")])
        self.assertEqual(numbered, 2)
        self.assertEqual(len(set(ids)), 3)
        k = "GEN|2021-01-28|같은|본문"
        self.assertEqual(ids[0], "C" + hashlib.sha1((k + "|#1").encode()).hexdigest()[:12])
        self.assertEqual(ids[1], "C" + hashlib.sha1((k + "|#2").encode()).hexdigest()[:12])

    def test_row_number_is_not_material(self):
        a, _ = make_ids([row(1, "가짜", "본문")])
        b, _ = make_ids([row(99, "가짜", "본문")])
        self.assertEqual(a, b)

    def test_norm(self):
        self.assertEqual(norm("  a \n\t b  "), "a b")
