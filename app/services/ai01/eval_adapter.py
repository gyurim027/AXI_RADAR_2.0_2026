"""공통 평가 틀(W05-06) 연결. 정답 목록은 만든 문장만 쓴다 (민원 원문·개인정보 X).

- run: 가린 요약 → 관련 여부 (data/eval/ai01_relevance_cases.csv, 맞음 기준 '같음')
- run_mask: 만든 민원 글 → 가린 글 (data/eval/ai01_mask_cases.csv, 가릴 꼴은 '안 들어감', 남길 장소는 '포함')
- ped_type(유형)은 유형 목록이 정해진 뒤 정답 목록을 더한다
"""
from __future__ import annotations

from app.services.ai01.classify import classify


def run(summary: str):
    decided = classify(summary)
    return decided[0] if decided else None


def run_mask(text: str):
    from app.services.ai01 import masking
    r = masking.mask("", text)
    return r.text if r.ok else None
