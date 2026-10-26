"""C-01 파일 받기: 받지 않는 파일."""
import unittest

from app.services.load.reader import LoadFileError, read_rows
from tests.test_load_fixtures import general, spp, xlsx


class ReaderTests(unittest.TestCase):
    def test_reads_rows(self):
        rows = read_rows(xlsx([spp(1), general(2)]))
        self.assertEqual([r.number for r in rows], [1, 2])
        self.assertEqual(rows[1].processed, "-")

    def test_rejects_changed_header(self):
        with self.assertRaises(LoadFileError) as cm:
            read_rows(xlsx([], header=("번호", "제목", "민원등록일", "민원처리일", "유형", "상세보기")))
        self.assertEqual(cm.exception.code, "bad_header")

    def test_rejects_swapped_header_order(self):
        with self.assertRaises(LoadFileError):
            read_rows(xlsx([], header=("민원제목", "번호", "민원등록일", "민원처리일", "유형", "상세보기")))

    def test_rejects_several_sheets(self):
        with self.assertRaises(LoadFileError) as cm:
            read_rows(xlsx([general(1)], sheets=2))
        self.assertEqual(cm.exception.code, "bad_sheets")

    def test_rejects_non_xlsx(self):
        with self.assertRaises(LoadFileError) as cm:
            read_rows(b"a,b,c\n1,2,3\n")
        self.assertEqual(cm.exception.code, "unreadable_file")
        self.assertNotIn("1,2,3", cm.exception.message)
