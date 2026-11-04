"""5장 칸별 만드는 규칙: 원본 한 줄 → 79 src_complaint 칸 (AI-01 칸·중복 표시·업로드 칸 제외).

원문(제목·본문)은 여기서 읽기만 하고, 돌려주는 값에는 규칙 가림을 마친 글자 칸만 담는다.
"""
from __future__ import annotations

import re
from datetime import date

from app.services.load.coords import Grid, locate
from app.services.load.ids import SPP_RE, detect_source
from app.services.load.masking import mask_text, pii_patterns
from app.services.load.reader import RawRow

GU_RE = re.compile(r"수정구|중원구|분당구")
DONG_RE = re.compile(r"([가-힣0-9]+동)\b")
DATE_RE = re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?")
PHOTO_RE = re.compile(r"\((\d+)/(\d+)\)\s*([CGS])\s*:\s*(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
TYPE_RE = re.compile(r"\(SPP-\d{4}-[0-9A-Z]+\)\s*(.+?)\s*신고입니다")
TRANSFER_RE = re.compile(r"이송기관\s*:\s*([^\s,]+)")


def nz(s: str | None) -> str | None:
    """빈 글자는 넣지 않고 NULL."""
    return s if s not in (None, "") else None


def tag(body: str, name: str) -> str | None:
    m = re.search(r"\[" + re.escape(name) + r"\]\s*:?\s*([^\n]*)", body or "")
    return nz(m.group(1).strip()) if m else None


def line(body: str, name: str) -> str | None:
    m = re.search(name + r"\s*:\s*([^\n]*)", body or "")
    return nz(m.group(1).strip()) if m else None


def parse_dt(s: str | None) -> str | None:
    """'YYYY-MM-DD[ HH:MM[:SS]]' 꼴만 받는다. 꼴이 다르면 NULL."""
    if not s:
        return None
    m = DATE_RE.search(s)
    if not m:
        return None
    y, mo, d, hh, mi, ss = m.groups()
    try:
        date(int(y), int(mo), int(d))
    except ValueError:
        return None
    out = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    if hh is not None:
        out += f" {int(hh):02d}:{mi}" + (f":{ss}" if ss else "")
    return out


def parse_date(s: str | None) -> str | None:
    v = parse_dt(s)
    return v[:10] if v else None


def build_record(row: RawRow, complaint_id: str, year: int, month: int, grid: Grid) -> dict:
    title, body = row.title or "", row.body or ""
    source = detect_source(title)
    spp = SPP_RE.search(title)

    m = TYPE_RE.match(title.lstrip())                    # 제목 맨 앞이 (SPP-…)일 때만 (79 기존 값과 같게)
    report_type = mask_text(nz(m.group(1).strip())) if m else None

    received = parse_date(row.received)
    processed = parse_date(row.processed) if row.processed not in ("", "-") else None
    days = None
    if received and processed:
        days = (date.fromisoformat(processed) - date.fromisoformat(received)).days

    loc = tag(body, "사고발생지역") or line(body, "위반장소")
    location = mask_text(loc)

    gu_m = GU_RE.search(location or "")
    pos = locate(body, grid)
    if pos["lat"] is None and location is None:
        pos["coord_method"] = "없음"                     # 좌표·위치 둘 다 없음. 위치만 있고 좌표가 없으면 주소 변환 대기(NULL)
    gu = gu_m.group(0) if gu_m else pos["grid_gu"]

    photos = PHOTO_RE.findall(body)
    first_photo = None
    if photos:
        first_photo = parse_dt(photos[0][3].replace("/", "-"))

    dong_m = DONG_RE.search(location or "")
    head = report_type or ("스마트국민제보 이송" if source == "스마트국민제보" else "일반 민원")
    tail = f"{gu or '구 미상'}" + (f" {dong_m.group(1)}" if dong_m else "")
    display_tag = f"{head} · {tail}"

    t = TRANSFER_RE.search(title)
    return {
        "complaint_id": complaint_id,
        "source_receipt_no": spp.group(0) if spp else None,
        "raw_position": f"{year}년 파일 · {month:02d}월 시트 · 번호 {row.number}",
        "source_type": source,
        "receipt_channel": nz(row.channel),
        "inflow_media": tag(body, "민원 유입 경로"),
        "report_type_raw": report_type,
        "received_date": received,
        "processed_date": processed,
        "has_processed_date": "Y" if processed else "N",
        "processing_days": days,
        "request_org": tag(body, "처리요청기관"),
        "transfer_org": t.group(1) if t else None,
        "location_text": location,
        "gu": gu,
        "admin_dong_name": pos["grid_dong"],
        "lat": pos["lat"],
        "lon": pos["lon"],
        "gid": pos["gid"],
        "coord_method": pos["coord_method"],
        "coord_accuracy": pos["coord_accuracy"],
        "photo_cnt": len(photos) or None,
        "first_photo_at": first_photo,
        "occurred_at": parse_dt(line(body, "발생일자")),
        "reported_at": parse_dt(line(body, "신고일자")),
        "display_tag": display_tag,
        "raw_pii_patterns": pii_patterns(title, body),
    }
