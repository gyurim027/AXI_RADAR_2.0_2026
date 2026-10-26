"""5~7장: 칸 만들기 · 규칙 가림 · 중복 표시 · 좌표 → 격자."""
import unittest

from app.services.load import dupes
from app.services.load.coords import Grid, cell_key, to_5179
from app.services.load.fields import build_record, parse_dt
from app.services.load.masking import has_pii, mask_text, pii_patterns
from app.services.load.reader import RawRow, read_rows
from tests.test_load_fixtures import GRID, POS_OUT, general, spp, xlsx


def rec(n_row):
    r = read_rows(xlsx([n_row]))[0]
    return build_record(r, "Cxxxxxxxxxxxx", 2025, 11, Grid(GRID))


class FieldTests(unittest.TestCase):
    def test_spp_record(self):
        r = rec(spp(7, phone="010-1234-5678"))
        self.assertEqual(r["source_receipt_no"], "SPP-2511-ABC0007")
        self.assertEqual(r["raw_position"], "2025년 파일 · 11월 시트 · 번호 7")
        self.assertEqual(r["source_type"], "안전신문고(SPP)")
        self.assertEqual(r["inflow_media"], "모바일")
        self.assertEqual(r["request_org"], "시 담당과")
        self.assertEqual(r["report_type_raw"], "횡단보도 불법 주정차")
        self.assertEqual((r["received_date"], r["processed_date"], r["has_processed_date"], r["processing_days"]),
                         ("2025-11-03", "2025-11-05", "Y", 2))
        self.assertEqual(r["photo_cnt"], 2)
        self.assertEqual(r["first_photo_at"], "2025-11-03 10:00:00")
        self.assertEqual(r["gu"], "분당구")
        self.assertEqual((r["gid"], r["coord_method"], r["coord_accuracy"]), ("G1", "원본 좌표(본문 위치값)", "원본 좌표"))
        self.assertEqual(r["admin_dong_name"], "정자동")
        self.assertIn("[휴대전화]", r["location_text"])
        self.assertNotIn("1234", r["location_text"])
        self.assertEqual(r["raw_pii_patterns"], "휴대전화")
        self.assertEqual(r["display_tag"], "횡단보도 불법 주정차 · 분당구 정자동")

    def test_general_without_position(self):
        r = rec(general(3))
        self.assertIsNone(r["processed_date"])
        self.assertEqual(r["has_processed_date"], "N")
        self.assertIsNone(r["processing_days"])
        self.assertEqual(r["coord_method"], "없음")
        self.assertIsNone(r["gid"])
        self.assertEqual(r["display_tag"], "일반 민원 · 구 미상")
        self.assertIsNone(r["raw_pii_patterns"])          # 빈 글자는 NULL

    def test_position_outside_grid(self):
        r = rec(spp(1, pos=POS_OUT))
        self.assertEqual((r["coord_method"], r["gid"], r["coord_accuracy"]), ("원본 좌표(성남 격자 밖)", None, None))
        self.assertIsNotNone(r["lat"])

    def test_address_only_waits_for_conversion(self):
        # 위치 글자는 있고 좌표가 없으면 이번 범위에서는 주소 변환을 하지 않고 비워 둔다 (NULL)
        r = rec(("1", "(SPP-2511-ZZZ) 가짜 신고입니다.", "2025-11-03", "-", "안전신문고 앱", "[사고발생지역]: 성남시 중원구 어딘가"))
        self.assertIsNone(r["coord_method"])
        self.assertEqual(r["gu"], "중원구")

    def test_date_parsing(self):
        self.assertEqual(parse_dt("2025.1.2 3:04"), "2025-01-02 03:04")
        self.assertEqual(parse_dt("2025-01-02"), "2025-01-02")
        self.assertIsNone(parse_dt("가짜"))
        self.assertIsNone(parse_dt("2025-13-40"))

    def test_masking_order_and_patterns(self):
        s = "12가3456 / 010-1234-5678 / a.b@c.kr / 044-300-1234 / 37.4010101"
        out = mask_text(s)
        self.assertEqual(out, "[차량번호] / [휴대전화] / [메일] / 044-300-1234 / 37.4010101")
        self.assertEqual(pii_patterns("12가3456", "a.b@c.kr"), "차량번호 · 메일")
        self.assertIsNone(pii_patterns("없음"))
        self.assertFalse(has_pii(out))
        self.assertTrue(has_pii("010-1234-5678"))


class DupeTests(unittest.TestCase):
    def test_dup_and_repeated(self):
        same = [RawRow(i, "같은 제목", "2025-11-01", "-", "기타", "같은 본문") for i in range(1, 4)]
        many = [RawRow(10 + i, "집단 제목", "2025-11-01", "-", "기타", f"본문{i}") for i in range(30)]
        spp_rows = [RawRow(100 + i, "(SPP-2511-A) 신고입니다", "2025-11-01", "-", "앱", f"본문{i}") for i in range(31)]
        marks = dupes.mark(same + many + spp_rows)
        self.assertEqual(marks[0], ("같은 행 3건", None))
        self.assertEqual(marks[3], (None, "같은 제목 30건"))
        self.assertEqual(marks[-1], (None, None))          # 안전신문고는 반복 제목에서 뺌


class CoordTests(unittest.TestCase):
    def test_projection_matches_grid_cid(self):
        # 01 grid_cell 의 cid 3832_7721 = (x // 250, y // 250), 중심점 37.371498 127.027058
        x, y = to_5179(37.371498, 127.027058)
        self.assertEqual((round((x - 125) / 250), round((y - 125) / 250)), (3832, 7721))
        self.assertEqual(cell_key(37.371498, 127.027058), (3832, 7721))

    def test_grid_miss(self):
        self.assertIsNone(Grid(GRID).find(37.7, 127.5))
