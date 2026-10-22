"""4장 민원ID: 'C' + SHA-1(재료 한 줄)의 앞 12자리. 다시 받아도 바뀌지 않는 값만 재료로 쓴다.

계산식은 79 complaint_id와 같아야 하므로 명세서 그대로 따른다.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Sequence

from app.services.load.reader import RawRow

SPP_RE = re.compile(r"SPP-\d{4}-[0-9A-Z]+")
SRC_SPP, SRC_SMT, SRC_GEN = "안전신문고(SPP)", "스마트국민제보", "일반 민원"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def body_line(body: str, name: str) -> str:
    """본문의 '이름: 내용' 줄 내용 (없으면 빈 글자)."""
    m = re.search(name + r"\s*:\s*([^\n]*)", body or "")
    return norm(m.group(1)) if m else ""


def detect_source(title: str) -> str:
    if SPP_RE.search(title or ""):
        return SRC_SPP
    if (title or "").startswith("스마트국민제보"):
        return SRC_SMT
    return SRC_GEN


def id_material(row: RawRow) -> list[str]:
    src = detect_source(row.title)
    if src == SRC_SPP:
        return ["SPP", SPP_RE.search(row.title).group(0)]
    if src == SRC_SMT:
        return ["SMT", body_line(row.body, "신고일자"), body_line(row.body, "위반장소"), norm(row.title)]
    return ["GEN", norm(row.received), norm(row.title), norm(row.body)]


def make_ids(rows: Sequence[RawRow]) -> tuple[list[str], int]:
    """행마다 민원ID를 만든다 (입력 순서 = 파일 안 순서). 돌려주는 값: (ID 목록, 순번이 붙은 행 수)."""
    keys = ["|".join(id_material(r)) for r in rows]
    total = Counter(keys)
    seen: Counter = Counter()
    ids, numbered = [], 0
    for k in keys:
        if total[k] >= 2:
            seen[k] += 1
            k = f"{k}|#{seen[k]}"
            numbered += 1
        ids.append("C" + hashlib.sha1(k.encode("utf-8")).hexdigest()[:12])
    return ids, numbered
