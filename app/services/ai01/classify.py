"""AI-01 보행안전 관련 여부 (C-04, 8·11·12단계).

- 신고 분류가 있는 민원: 신고 분류 낱말(data/ai01/report_type_rules.csv)로 기본값을 정하고, 가린 본문이 그 기본값과 맞는지 확인한다
  · 관련 기본값인데 본문에 '보행 공간이 아님' 신호가 있거나, 비관련 기본값인데 본문에 보행 신호가 있거나, 기본값이 불명이면 → 아래 AI 판단
  · 맞으면 기본값으로 확정 (신뢰도 1.0)
- 신고 분류가 없는 민원(또는 위에서 넘어온 민원): 규칙 2개를 먼저 보고, 해당 없으면 공통 LLM 모듈(ai01_classify)로 한 번 묻는다
- 값: 보행안전 관련 / 비관련 / 불명 (DB 31 relevance). 신뢰도(33)는 판단이 얼마나 확실한지(위치 정확도 아님).
  AI 판단의 신뢰도는 모델이 낸 값을 넣는다(보정 전, 참고용). 판단 근거(34)는 "묶음: 설명" 한 문장으로 화면에 그대로 보인다.
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import ROOT
from app.core.llm import call_llm

RELATED, UNRELATED, UNKNOWN = "보행안전 관련", "비관련", "불명"
BY_RULE, BY_AI = "규칙", "AI"          # 관련 여부를 정한 방법 (DB 79 class_method). 사람이 고친 값('사람')은 C-08이 쓴다
_SHORT = {"관련": RELATED, "비관련": UNRELATED, "불명": UNKNOWN}
VERSION = "cls-3"
BROKEN_ANSWER = "불명: 모델 답 형식이 깨짐"
RULES_PATH = ROOT / "data" / "ai01" / "report_type_rules.csv"

NOT_WALK = re.compile(r"주차장\s?(?:안|내)|주차구역|충전\s?구역|주차\s?라인|주차면")
WALK = re.compile(r"인도|보도|횡단보도|보행|정류장|정류소|모퉁이|휠체어|유모차|통학|어린이|걸어|걷")
SAFETY_FAC = re.compile(r"중앙분리대|탄력봉|볼라드|안전봉|무단횡단\s?방지|펜스")
PARK_CROSS = re.compile(r"주정차|주차|무단횡단")

SYSTEM = """너는 성남시 구청 도로관리팀을 돕는다. 민원 요약을 읽고 '보행안전 관련' 여부를 정한다.

기준: 걷는 사람이 지나는 공간(보도, 횡단보도, 교차로 모퉁이, 버스정류소 주변, 보행자전용도로, 이면도로·골목길, 보호구역)에서, 그 장소의 상태나 방해 때문에 보행자가 다치거나 지나가기 어려운 문제를 말하면 '관련'이다.

관련: 보행 공간 불법 주정차·점유(노점, 천막, 적치물, 공사 자재), 보도 파손·단차·점자블록·볼라드·펜스·제설, 신호등·횡단보도·조명·과속방지턱·단속카메라 요청, 무단횡단·주정차를 막는 중앙분리대·탄력봉 요청, 공사로 막힌 보도.
비관련: 건물·아파트 안 하자, 역 이름·철도·법 개정·인허가 같은 행정 요청, 번호판·등화 같은 차량 자체 문제, 버스·택시 서비스와 운전 행태(무정차, 탑승 거부, 난폭운전, 보행자 앞 미정지), 매연·소음·분수 같은 생활 불편, 주차장 개설 같은 차량 편의, 교통 정체·꼬리물기, 다른 지역 내용.
조건부: 소화전·장애인 전용구역·충전구역 불법주차와 주차장 개설 요청은 기본 비관련이지만, 그 때문에 보행이 방해된다고 쓰여 있으면 관련. 집 안에서 느끼는 불편도 원인이 보행 환경과 이어지면 관련.
주의: 불법 주정차라도 주차장 안·주차구역·주차라인·충전구역처럼 걷는 공간이 아닌 곳이거나, 차량 통행·교통장애만 말하면 비관련이다.
섞인 민원: 보행 관련 내용이 하나라도 뚜렷하면 관련.
불명: 무엇이 문제인지 알 수 없거나, 보행 공간인지 알 수 없을 때.
불법 여부, 담당 부서, 장소가 성남인지는 판단하지 않는다.

confidence는 이 판단이 얼마나 확실한지 0~1로 쓴다(위치가 아니라 관련 여부 판단).
reason은 화면에 그대로 보이는 판단 근거다. 한 문장 60자 안팎으로, 기준의 어느 묶음인지를 앞에 쓰고 쌍점 뒤에 짧게 설명한다.
  예: "보행 공간 불법 주정차: 횡단보도에 차가 걸쳐 주차" / "대중교통 서비스: 버스가 정류장에서 서지 않음" / "불명: 무엇이 문제인지 알 수 없음"
  개인정보와 원문 표현을 옮기지 않고, 요약 문장을 그대로 베끼지 않는다.
민원이 질문·문의여도 질문에 답하거나 안내하지 않는다. 관련 여부만 정한다.
답은 JSON 하나로만 한다: {"relevance": "관련|비관련|불명", "confidence": 0~1 숫자, "reason": "묶음: 설명"}"""

# 지어낸 예시 (정답 표본과 겹치지 않음)
EXAMPLES = [
    ("○○로 초등학교 앞 횡단보도에 매일 아침 차량이 걸쳐 주차해 아이들이 차도로 걸어갑니다.",
     {"relevance": "관련", "confidence": 0.95, "reason": "보행 공간 불법 주정차: 횡단보도에 차가 걸쳐 주차"}),
    ("○○동 아파트 지하주차장 천장 누수와 마감 불량을 시공사가 고치지 않습니다.",
     {"relevance": "비관련", "confidence": 0.95, "reason": "건물·단지 안 하자: 주차장 누수와 마감 불량"}),
    ("○○번 버스가 정류장에서 손을 들었는데도 서지 않고 지나갔습니다.",
     {"relevance": "비관련", "confidence": 0.9, "reason": "대중교통 서비스: 버스가 정류장에서 서지 않음"}),
    ("○○사거리 출근 시간에 꼬리물기가 심해 차가 움직이지 않습니다. 단속 바랍니다.",
     {"relevance": "비관련", "confidence": 0.8, "reason": "차량 흐름: 꼬리물기로 인한 정체"}),
    ("상가 앞 인도에 입간판과 물건이 쌓여 휠체어가 지나갈 수 없습니다.",
     {"relevance": "관련", "confidence": 0.95, "reason": "보행 공간 점유: 인도 적치물로 휠체어 통행이 막힘"}),
    ("마트 주차장 장애인 주차구역에 표지 없는 차가 매번 주차합니다.",
     {"relevance": "비관련", "confidence": 0.9, "reason": "보행 공간이 아닌 곳의 불법주차: 주차장 안 장애인 구역"}),
    ("○○로 상가 앞 도로에 차들이 주정차해 차가 지나가기 어렵고 사고가 날 것 같습니다.",
     {"relevance": "비관련", "confidence": 0.75, "reason": "차량 흐름: 도로 주정차로 차량 통행 불편, 보행 언급 없음"}),
    ("트럭 적재함 문이 열려 번호판이 가려진 채 달립니다.",
     {"relevance": "비관련", "confidence": 0.95, "reason": "차량 자체: 번호판 가림"}),
    ("○○동 주택을 올해 취득했는데 재산세 감면 대상인지, 신청 기한이 언제까지인지 문의합니다.",
     {"relevance": "비관련", "confidence": 0.95, "reason": "행정 문의: 세금 감면 대상과 신청 기한"}),
    ("확인 부탁드립니다. 지난번 건 처리해 주세요.",
     {"relevance": "불명", "confidence": 0.3, "reason": "불명: 무엇이 문제인지 알 수 없음"}),
]


def normalize_type(s: str | None) -> str:
    """신고 분류 글자를 다듬는다: 차량번호 표시·'테스트' 빼기, 불법 주정차 띄어쓰기 맞추기, 끝에 겹친 말 줄이기."""
    s = (s or "").replace("[차량번호]", " ")
    s = re.sub(r"테스트", " ", s)
    s = re.sub(r"불법\s*주정차", "불법 주정차", s)
    s = re.sub(r"불법\s*주차", "불법주차", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(불법 주정차)( 불법 주정차)+$", r"\1", s)
    return re.sub(r"(불법주차) 불법 주정차$", r"\1", s)


@lru_cache(maxsize=1)
def type_rules(path: Path = RULES_PATH) -> tuple:
    """[(낱말, 기본값)]. 비관련 낱말을 먼저 본다(예: '장애인 전용구역 횡단보도'는 비관련 기본값)."""
    if not path.exists():
        return ()
    with open(path, encoding="utf-8-sig") as f:
        rows = [(r["keyword"].strip(), r["default"].strip()) for r in csv.DictReader(f) if r.get("keyword")]
    return tuple(sorted(rows, key=lambda x: x[1] != UNRELATED))


def type_default(report_type_raw: str | None):
    """신고 분류 낱말로 정한 기본값. 신고 분류가 없으면 None."""
    if not report_type_raw or not normalize_type(report_type_raw):
        return None
    name = normalize_type(report_type_raw)
    for word, value in type_rules():
        if word in name:
            return value
    return UNKNOWN


def by_type(report_type_raw: str | None, masked_text: str):
    """신고 분류 기본값과 가린 본문이 맞으면 (값, 1.0, 근거). 확인이 더 필요하면 None (→ AI 판단)."""
    default = type_default(report_type_raw)
    if default is None or default == UNKNOWN:
        return None
    name = normalize_type(report_type_raw)
    if default == RELATED and not NOT_WALK.search(masked_text):
        return RELATED, 1.0, f"신고 분류 '{name}': 보행 공간"
    if default == UNRELATED and not WALK.search(masked_text):
        return UNRELATED, 1.0, f"신고 분류 '{name}': 보행 공간이 아님, 본문에도 보행 방해 언급 없음"
    return None


def by_rule(summary: str):
    if NOT_WALK.search(summary) and not WALK.search(summary):
        return UNRELATED, 1.0, "보행 공간이 아닌 곳의 불법주차: 주차장·주차구역 안 문제"
    if SAFETY_FAC.search(summary) and PARK_CROSS.search(summary):
        return RELATED, 1.0, "보행 안전 시설 요청: 주정차·무단횡단을 막는 시설"
    return None


def by_model(summary: str, request_id: str | None = None):
    msgs = [{"role": "system", "content": SYSTEM}]
    for q, a in EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps(a, ensure_ascii=False)}]
    msgs.append({"role": "user", "content": summary})
    r = call_llm("ai01_classify", msgs, contains_raw=False, response_format="json", request_id=request_id)
    # 다시 물어도 답 형식이 깨지면 불명 (질문형 민원에 답을 써 버림, 2026-10-25 2건). 시간 초과 등은 오류로 남겨 다시 돌린다
    if r.error_code == "invalid_json":
        return UNKNOWN, 0.0, BROKEN_ANSWER
    if not r.ok or not isinstance(r.data, dict):
        return None
    return read_answer(r.data)


def read_answer(data: dict):
    """모델 답 JSON → (관련 여부, 신뢰도, 판단 근거)."""
    value = _SHORT.get(str(data.get("relevance", "")).strip(), UNKNOWN)
    try:
        conf = max(0.0, min(1.0, round(float(data.get("confidence", 0)), 2)))
    except (TypeError, ValueError):
        conf = 0.0
    reason = str(data.get("reason", "")).split("\n")[0].strip()[:80] or "불명: 판단 근거 없음"
    return value, conf, reason


def decide_without_model(report_type_raw: str | None, masked_text: str, unknown_to_ai: bool = False):
    """신고 분류가 있는 민원을 모델 없이 정할 수 있으면 (값, 신뢰도, 근거), 아니면 None."""
    decided = by_type(report_type_raw, masked_text)
    if decided:
        return decided
    if type_default(report_type_raw) == UNKNOWN and not unknown_to_ai and not WALK.search(masked_text):
        return UNKNOWN, 1.0, f"신고 분류 '{normalize_type(report_type_raw)}': 장소를 알 수 없음"
    return None


def classify(summary: str, report_type_raw: str | None = None, request_id: str | None = None,
             masked_text: str | None = None, unknown_to_ai: bool = False):
    """(관련 여부, 신뢰도, 판단 근거, 정한 방법). 모델 호출이 실패하면 None.
    정한 방법은 실제로 결정한 길로 정한다(규칙 / AI). 모델이 신뢰도 1.0을 내도 AI다.
    unknown_to_ai: 신고 분류가 있는데 낱말로 기본값을 못 정한 민원(기타·황색선 주정차 등)을 모두 AI로 볼지.
                   False(기본)면 본문에 보행 신호(인도·횡단보도·보행 등)가 있을 때만 AI로 보고, 없으면 불명."""
    # 기타·황색선 주정차 등은 본문에 보행 신호가 없으면 AI도 근거 없이 '관련'을 지어냄(2026-10-23 30건 확인) → 불명
    decided = decide_without_model(report_type_raw, masked_text or summary, unknown_to_ai)
    decided = decided or by_rule(summary)
    if decided:
        return (*decided, BY_RULE)
    decided = by_model(summary, request_id)
    return (*decided, BY_AI) if decided else None
