"""공통 평가 틀(W05-06) 연결: 가린 요약을 넣으면 관련 여부를 돌려준다.

정답 목록 예 (민원 원문·개인정보 없이 가린 요약만):
    case_id | 입력(가린 요약) | 기대 답(보행안전 관련 / 비관련 / 불명) | 맞음 기준(같음)
"""
from __future__ import annotations

from app.services.ai01.classify import classify


def run(summary: str):
    decided = classify(summary)
    return decided[0] if decided else None
