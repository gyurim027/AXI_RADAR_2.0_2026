"""C-02 같은 민원 · 집단 민원 표시 (5장 29·30번). 지우지 않고 표시만 한다.

- 중복_표시: 제목·등록일·본문이 모두 같은 행이 N(≥2)건이면 '같은 행 N건'
- 반복_제목: 안전신문고가 아닌데 같은 제목이 N(≥30)건이면 '같은 제목 N건'
올린 파일 안에서만 센다 (명세서 11장 미결 1).
"""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from app.services.load.ids import SRC_SPP, detect_source
from app.services.load.reader import RawRow

REPEAT_MIN = 30


def mark(rows: Sequence[RawRow]) -> list[tuple[str | None, str | None]]:
    same = Counter((r.title, r.received, r.body) for r in rows)
    title = Counter(r.title for r in rows if detect_source(r.title) != SRC_SPP)
    out = []
    for r in rows:
        n = same[(r.title, r.received, r.body)]
        k = title.get(r.title, 0) if detect_source(r.title) != SRC_SPP else 0
        out.append((f"같은 행 {n}건" if n >= 2 else None, f"같은 제목 {k}건" if k >= REPEAT_MIN else None))
    return out
