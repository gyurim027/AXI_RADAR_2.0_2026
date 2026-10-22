"""6장 규칙 가림: 저장하는 글자 칸(신고유형_원문·위치_원문)에 차량번호 → 휴대전화 → 메일 순서로 적용하고,
같은 세 꼴을 제목+본문 원문에서 찾아 원문_개인정보_패턴에 '꼴 이름'만 적는다."""
from __future__ import annotations

import re

# (꼴 이름, 찾는 꼴, 바꿀 글자) — 순서 고정
RULES = [
    ("차량번호", re.compile(r"\d{2,3}\s?[가-힣]\s?\d{4}"), "[차량번호]"),
    ("휴대전화", re.compile(r"(?<![\d.])01[016789]-?\d{3,4}-?\d{4}(?![\d.])"), "[휴대전화]"),
    ("메일", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[메일]"),
]


def mask_text(s: str | None) -> str | None:
    if s is None:
        return None
    for _name, rx, repl in RULES:
        s = rx.sub(repl, s)
    return s


def pii_patterns(*texts: str) -> str | None:
    joined = "\n".join(t or "" for t in texts)
    found = [name for name, rx, _ in RULES if rx.search(joined)]
    return " · ".join(found) if found else None


def has_pii(s: str | None) -> bool:
    """9장 검사 6: 저장 칸에 세 꼴이 남아 있는가."""
    return bool(s) and any(rx.search(s) for _n, rx, _r in RULES)
