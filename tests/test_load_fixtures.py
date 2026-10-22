"""민원 적재 시험용 가짜 자료 (실제 민원 글자는 쓰지 않는다)."""
import datetime as dt
import io
import unittest
from unittest import mock

import openpyxl

from app.services.load.reader import HEADER

GRID = [("G1", 37.371498, 127.027058, "분당구", "정자동"), ("G2", 37.371498, 127.030058, "분당구", "정자동")]
SOURCE = "성남데이터넷 연도별 민원 현황 (공공누리 제1유형)"
POS_IN = "위도:37.371498 경도:127.027058"
POS_OUT = "위도:37.700000 경도:127.500000"          # 성남 격자 밖


def xlsx(rows, header=HEADER, sheets=1) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    for _ in range(sheets - 1):
        wb.create_sheet("두번째")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def spp(n, receipt="SPP-2511-ABC000%d", received="2025-11-03", processed="2025-11-05", pos=POS_IN, phone=""):
    body = (f"[민원 유입 경로]: 모바일\n[처리요청기관]: 시 담당과\n[사고발생지역]: 성남시 분당구 정자동 {n}번지 {phone}\n"
            f"* 발생지역 {pos}\n(1/2) C : 2025/11/03 10:00:00\n(2/2) S : 2025/11/03 10:00:05")
    return (n, f"({receipt % n}) 횡단보도 불법 주정차 신고입니다.", received, processed, "안전신문고 앱", body)


def general(n, title="가짜 제목", body="가짜 본문", received="2025-11-04", processed="-"):
    return (n, f"{title}{n}", received, processed, "기타", body)


def meta(**kw):
    from app.services.load.pipeline import UploadMeta
    base = dict(data_name="민원 2025-11", source=SOURCE, ref_date=dt.date(2025, 11, 30),
                period_start=dt.date(2025, 11, 1), period_end=dt.date(2025, 11, 30))
    base.update(kw)
    return UploadMeta(**base)


class BaseLoadCase(unittest.TestCase):
    """적재 시험의 기반: AI-01 본체가 합쳐진 트리에서도 시험이 진짜 모델을 부르지 않도록 가짜 함수로 고정한다.
    진짜 함수를 거치는 시험은 tests/test_load_ai01_real.py (여기서 상속하지 않음)."""

    def setUp(self):
        from app.services.load import ai01_port as port
        from app.services.load.ai01_stub import ComplaintInput, refine_complaints

        def resolve(refine=None):
            return port.Backend(refine, ComplaintInput, "custom") if refine else port.Backend(refine_complaints, ComplaintInput, "stub")
        p = mock.patch.object(port, "resolve_backend", side_effect=resolve)
        p.start()
        self.addCleanup(p.stop)
