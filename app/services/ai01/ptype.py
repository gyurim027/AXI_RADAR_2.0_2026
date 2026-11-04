"""AI-01 민원 유형 (C-05, DB 79 ped_type). 보행안전 '관련' 민원에만 하나 붙인다. 비관련·불명은 비운다.

유형 목록: ISS-016 확정(2026-10-24) — 보행을 막거나 위험하게 하는 '대상' 한 기준으로 나눈 9개.
겹침 규칙
  1. 한 민원에 유형은 하나
  2. 대상이 여럿이면 민원이 고쳐 달라는 대상. 그래도 둘이면 목록 앞쪽
  3. 결과(시야 가림, 차도로 걸음)가 아니라 원인 대상으로 나눈다
  4. 해결책을 요청한 민원도 그 해결책이 막으려는 문제의 원인으로 나눈다 (주정차 때문에 탄력봉 요청 → 주정차, 2026-10-24)
정하는 순서
  - 신고 분류가 불법 주정차·주차면 규칙으로 '주정차' (안전신문고 대부분)
  - 그 밖은 가린 요약을 공통 LLM 모듈(ai01_type, 내부 모델)로 한 번 묻는다. 목록 밖 답이나 실패면 비운다(None)
"""
from __future__ import annotations

import json
import re

from app.core.llm import call_llm

VERSION = "type-2"
TYPES = ("주정차", "점유", "공사", "노면", "보행로", "시설", "신호", "조명", "기타")
PARKING = re.compile(r"주정차|주차")

SYSTEM = """너는 성남시 구청 도로관리팀을 돕는다. 보행안전 관련 민원 요약을 읽고 유형을 하나 고른다.
유형은 '무엇이 보행을 막거나 위험하게 하는가(대상)'로 나눈다.

주정차: 차가 보행 공간(인도, 횡단보도, 교차로 모퉁이, 버스정류소, 보호구역)에 서 있다
점유: 물건·영업·이동수단이 보행 공간을 차지한다 (적치물, 노점, 입간판, 천막, 옥외광고물, 방치된 PM·자전거)
공사: 공사가 보행 공간을 막거나 위험하게 한다 (공사로 막힌 보도, 공사 자재, 굴착 뒤 복구 안 됨)
노면: 걷는 바닥이 망가졌거나 미끄럽다 (보도블록 파손·들뜸, 단차, 포트홀, 점자블록 훼손, 고인 물, 제설)
보행로: 걸을 공간이 없거나 좁거나 끊겼다 (보도 없음, 보도 폭 부족, 보도 단절, 보도 신설·확장 요청)
시설: 보행 안전시설 자체가 없거나 고장 났거나 잘못 놓였다 (볼라드, 펜스, 가드레일, 반사경, 과속방지턱, 고원식 횡단보도, 중앙분리대, 탄력봉, 무단횡단 방지시설, 횡단보도 노면표시)
신호: 보행 신호가 없거나 짧거나 고장 났다 (보행 신호등 신설·고장, 녹색시간 부족, 잔여시간 표시기, 음향신호기, 바닥 신호등)
조명: 걷는 길이 어둡다 (가로등·보안등 고장·부족)
기타: 보행안전 관련이지만 위 8개에 맞지 않는다

규칙:
1. 하나만 고른다.
2. 대상이 여럿이면 민원이 고쳐 달라고 하는 대상을 고른다. 그래도 둘이면 위 목록에서 앞쪽을 고른다.
3. 결과가 아니라 원인으로 고른다. 예: 주차한 차가 교차로 시야를 가림 → 주정차.
4. 해결책을 요청한 민원도 그 해결책이 막으려는 문제의 원인으로 고른다. 예: 불법 주정차 때문에 탄력봉 설치 요청 → 주정차. 시설은 시설 자체가 무너졌거나 고장 났거나, 다른 원인 없이 시설이 없어 위험할 때만 고른다.
reason은 화면에 보이는 한 문장 40자 안팎이다. 개인정보와 원문 표현을 옮기지 않는다.
답은 JSON 하나로만 한다: {"ped_type": "유형", "reason": "설명"}"""

# 지어낸 예시 (정답 표본과 겹치지 않음)
EXAMPLES = [
    ("○○초등학교 앞 횡단보도에 아침마다 차가 걸쳐 주차해 아이들이 차도로 걸어갑니다.",
     {"ped_type": "주정차", "reason": "횡단보도에 걸친 주차"}),
    ("○○로 상가 앞 인도에 입간판과 물건이 쌓여 휠체어가 지나갈 수 없습니다.",
     {"ped_type": "점유", "reason": "인도 위 입간판과 적치물"}),
    ("○○동 보도블록이 들떠 있어 걷다가 넘어질 뻔했습니다. 보수 바랍니다.",
     {"ped_type": "노면", "reason": "보도블록 들뜸"}),
    ("○○길은 보도가 없어 아이들이 차도로 등교합니다. 보도를 만들어 주세요.",
     {"ped_type": "보행로", "reason": "보도가 없어 차도로 걸음"}),
    ("불법 주정차 때문에 ○○로 중앙선에 탄력봉을 설치해 주세요.",
     {"ped_type": "주정차", "reason": "불법 주정차를 막는 탄력봉 설치 요청"}),
    ("○○초등학교 앞 인도 펜스가 기울어져 넘어질 것 같습니다. 보수해 주세요.",
     {"ped_type": "시설", "reason": "인도 펜스가 기울어짐"}),
    ("○○사거리 횡단보도 보행 신호가 너무 짧아 어르신이 다 건너지 못합니다.",
     {"ped_type": "신호", "reason": "보행 녹색시간 부족"}),
]


def by_report_type(report_type_raw: str | None):
    """신고 분류가 불법 주정차·주차면 '주정차' (모델 없이)."""
    if report_type_raw and PARKING.search(report_type_raw):
        return "주정차"
    return None


def by_model(summary: str, request_id: str | None = None):
    msgs = [{"role": "system", "content": SYSTEM}]
    for q, a in EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps(a, ensure_ascii=False)}]
    msgs.append({"role": "user", "content": summary})
    r = call_llm("ai01_type", msgs, contains_raw=False, response_format="json", request_id=request_id)
    if not r.ok or not isinstance(r.data, dict):
        return None
    value = str(r.data.get("ped_type", "")).strip()
    return value if value in TYPES else None


def decide_type(summary: str | None, report_type_raw: str | None = None, request_id: str | None = None):
    """관련 민원의 유형. 정하지 못하면 None."""
    return by_report_type(report_type_raw) or (by_model(summary, request_id) if summary else None)
