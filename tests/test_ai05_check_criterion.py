"""W04-19 법령 색인 원문 대조 스크립트 시험 (가짜 색인). 실행: uv run python -m pytest tests/test_ai05_check_criterion.py"""
import unittest

from app.services.ai05.rag import LawIndex
from scripts.ai05_check_criterion import check


def _c(law, art, i):
    return {"chunk_id": i, "law_name": law, "article": art, "text": f"{law} {art}", "status": "시행 중", "cite": f"{law} {art}"}


IX = LawIndex([_c("도로교통법", "제32조", 1), _c("도로교통법", "제33조", 2), _c("재난 및 안전관리 기본법", "제66조의10", 3),
               _c("재난 및 안전관리 기본법 시행령", "제73조의8", 4)])


def row(cid, name, arts, kind="법령", used=""):
    return {"criterion_id": cid, "종류": kind, "이름": name, "조항·만든 곳": arts, "RADAR에서 쓴 곳": used, "확인 수준": "원문 확인"}


class CheckTests(unittest.TestCase):
    def test_states(self):
        res = {r["criterion_id"]: r for r in check([
            row("A", "도로교통법 (법률 제1호)", "제32조~제33조", used="T18"),
            row("G", "같은 법 (법률 제1호)", "제33조"),
            row("B", "도로교통법", "제32조, 제99조"),
            row("C", "자전거 이용 활성화에 관한 법률 (자전거법)", "제3조", used="T34"),
            row("D", "도로교통법", "법 전체"),
            row("E", "TAAS 교통사고분석시스템", "-", kind="공식문서"),
            row("F", "재난 및 안전관리 기본법", "제66조의10 (시행령 제73조의8)"),
        ], IX)}
        self.assertEqual(res["A"]["확인 상태"], "확인됨")
        self.assertEqual(res["A"]["T 코드"], "T18")
        self.assertEqual((res["B"]["확인 상태"], res["B"]["없는 조문"]), ("일부 없음", "제99조"))
        self.assertEqual(res["C"]["확인 상태"], "원문 없음")
        self.assertEqual(res["D"]["확인 상태"], "조문 표기 없음")
        self.assertEqual(res["E"]["확인 상태"], "대조 대상 아님")
        self.assertEqual(res["F"]["확인 상태"], "확인됨")                       # 시행령 조문은 시행령에서 찾음
        self.assertIn("시행령", res["F"]["메모"])
        self.assertEqual((res["G"]["법령"], res["G"]["확인 상태"]), ("도로교통법", "확인됨"))   # '같은 법' = 앞 줄


if __name__ == "__main__":
    unittest.main()


class StandardCsvTests(unittest.TestCase):
    def test_keep_only_pedestrian_sets(self):
        import tempfile
        from pathlib import Path
        from app.services.ai05.extract import read_standard_csv
        head = "데이터셋일련번호,데이터셋명,제공범위내용,관계법령내용,소관기관명,제공기관명,제공시스템명,갱신주기,항목번호,항목명,필수여부,항목설명,허용값,단위설명,예시값\n"
        body = ("1,주차장정보,a,b,c,d,e,반기,1,주차장관리번호,Y,설명,,,\n"
                "143,자전거도로,범위,자전거법,행정안전부,지자체,-,연간,1,노선명,Y,노선 이름,,,\n"
                "143,자전거도로,범위,자전거법,행정안전부,지자체,-,연간,2,자전거도로종류,Y,종류,전용·겸용,,\n")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "정책자료" / "공공데이터 제공 표준(20251001).csv"
            p.parent.mkdir()
            p.write_text(head + body, encoding="utf-8-sig")
            docs = read_standard_csv(p)
        self.assertEqual([x["annex"] for x in docs], ["143번 자전거도로"])        # 1번 주차장은 뺌
        self.assertEqual((docs[0]["law_name"], docs[0]["effective"], docs[0]["group"]), ("공공데이터 제공 표준", "2025-10-01", "정책자료"))
        self.assertIn("2. 자전거도로종류 (필수 Y): 종류 / 허용값: 전용·겸용", docs[0]["text"])
