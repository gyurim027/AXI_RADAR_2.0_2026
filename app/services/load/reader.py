"""C-01 파일 받기: 성남데이터넷 '민원 상세정보 현황' 엑셀 한 달치를 읽는다.

- 파일은 메모리에서만 읽고 디스크에 저장하지 않는다 (민원 파일 원본 보관 안 함, ISS-032).
- 칸 이름 6개가 다르거나 시트가 하나가 아니면 받지 않는다.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import BinaryIO

HEADER = ("번호", "민원제목", "민원등록일", "민원처리일", "유형", "상세보기")


class LoadFileError(Exception):
    """받지 않는 파일. message에는 원문을 넣지 않는다."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class RawRow:
    number: int
    title: str
    received: str
    processed: str
    channel: str
    body: str


def _text(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)


def read_rows(source: bytes | BinaryIO) -> list[RawRow]:
    import openpyxl

    stream = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    try:
        wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
    except Exception as e:
        raise LoadFileError("unreadable_file", "엑셀(xlsx) 파일을 열 수 없습니다.") from e
    try:
        if len(wb.worksheets) != 1:
            raise LoadFileError("bad_sheets", "시트가 하나인 파일만 받습니다.")
        it = wb.worksheets[0].iter_rows(values_only=True)
        head = next(it, None)
        if head is None or tuple(_text(c).strip() for c in head[:6]) != HEADER or any(c not in (None, "") for c in head[6:]):
            raise LoadFileError("bad_header", "칸 이름 6개(번호·민원제목·민원등록일·민원처리일·유형·상세보기)가 맞지 않습니다.")
        rows: list[RawRow] = []
        for i, r in enumerate(it, start=2):
            cells = list(r[:6]) + [None] * (6 - len(r))
            if all(c in (None, "") for c in cells):
                continue
            try:
                num = int(float(_text(cells[0])))
            except ValueError:
                raise LoadFileError("bad_row", f"{i}번째 줄의 번호가 숫자가 아닙니다.")
            rows.append(RawRow(num, _text(cells[1]), _text(cells[2]).strip(), _text(cells[3]).strip(),
                               _text(cells[4]).strip(), _text(cells[5])))
        return rows
    finally:
        wb.close()
