"""AI-05 평가용 어댑터 (W05-06 공통 평가 틀에 넣는 함수).

입력이 T + 숫자(예: T18)면 문제 유형 코드로(대응표 경로), 아니면 질문 글자로(검색 경로) 부른다.
결과는 찾은 조문의 인용 표시(cite) 목록(순위 순서). 못 찾으면 빈 목록.
"""
from __future__ import annotations

import re
from functools import lru_cache

from app.services.ai05.service import LawService

TYPE_CODE = re.compile(r"^T\d{2}$")


@lru_cache(maxsize=1)
def _svc() -> LawService:
    return LawService()


def run(text: str, k: int = 5) -> list[str]:
    text = (text or "").strip()
    if TYPE_CODE.match(text):
        r = _svc().related_articles(text, None, k, False)
    else:
        r = _svc().related_articles(None, text, k, False)
    return [it["cite"] for it in r.get("items", [])]
