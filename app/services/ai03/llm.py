"""4단계: LLM은 '검색어'만 만든다. 좌표는 절대 만들지 않는다.

호출은 공통 LLM 모듈(app/core/llm.py, 작업 ai03_refine)로 한다. 프롬프트·캐시·검색어 후처리만 여기에 둔다.
"""
import json
import re
import os
from app.core.llm import call_llm, task_config
from . import config as C
from .config import OUT

_cache_path = OUT / "llm_cache.json"
_cache = json.loads(_cache_path.read_text(encoding="utf-8")) if _cache_path.exists() else {}


def save_cache():
    _cache_path.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")

SYSTEM = """너는 성남시 위치 글자를 '브이월드 장소 검색'이 찾을 수 있는 검색어로 다듬는 도우미다.
규칙:
- 좌표 숫자는 절대 만들지 마라. 검색어만 만든다.
- 약칭은 정식 이름으로 (초교→초등학교, 동사무소·주민센타→행정복지센터, 여중고→여자중학교 등).
- '사거리, 삼거리, 단일로, 앞, 후문, 정문, 주변, 부근' 같은 꼬리말은 검색어에서 뺀다.
- 아파트 동 번호(101동)는 빼고 단지 이름만 남긴다.
- 확신이 없으면 검색어를 지어내지 말고 비워라.
- 반드시 JSON 하나만 출력한다. 다른 말 금지.
출력 형식:
{"queries": ["검색어1", "검색어2"], "place_type": "학교", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "한 줄 설명"}
칸 설명:
- queries: 서로 다른 검색어 최대 3개. 정식 이름, 짧은 이름, 흔히 부르는 이름처럼 서로 달라야 한다. 같은 말을 반복하지 마라
- 검색어에 도로 이름(○○로, ○○번길)이나 '근처, 옆, 앞, 단속장소' 같은 말을 넣지 마라
- place_type: 학교|공공기관|아파트|상가·건물|종교시설|공원|교통시설|도로|기타 중 하나
- road_only: '광장로', '마지로'처럼 도로 이름 하나만 있을 때만 true. 학교·건물·아파트·관공서 이름이 하나라도 있으면 반드시 false
- 교차로명이라도 건물·시설 이름이 있으면 그 이름을 queries에 넣는다 (예: '하원초교 삼거리' → ['하원초등학교'])
- segment: A~B 사이처럼 구간이면 true
- no_location: 위치 정보가 아니면 true
- outside_seongnam: 성남시 밖이면 true
- 검색어에 구 이름(중원구 등), '교차로', '보행신호', '부근', '주변'을 절대 넣지 마라. 시설 이름만 쓴다.
- 원래 이름을 다른 이름으로 바꾸지 마라 (중원보건소 → 보건센터 같은 일반화 금지).
예시: "코멕스 삼거리" → {"queries": ["코멕스"], "place_type": "상가·건물", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "꼬리말 제거"}
예시: "성일여중고 사거리" → {"queries": ["성일여자중학교", "성일여자고등학교"], "place_type": "학교", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "여중고는 여자중학교·여자고등학교"}
예시: "단대오거리2번출구단일로" → {"queries": ["단대오거리역"], "place_type": "교통시설", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "지하철역 출구 근처"}
예시: "야탑제1환승공영주차장 입구부근" → {"queries": ["야탑역환승주차장", "야탑제1공영주차장", "야탑공영주차장"], "place_type": "교통시설", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "주차장 이름 변형"}
예시: "판교로256번길 환상어린이공원 주변" → {"queries": ["환상어린이공원"], "place_type": "공원", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "도로 이름 빼고 공원 이름만"}
예시: "알파리움국민은행 옆" → {"queries": ["알파리움", "국민은행 알파리움"], "place_type": "상가·건물", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "건물 이름이 더 특정적"}
예시: 원래 글자 "금광2동사무소" → {"queries": ["금광2동행정복지센터", "금광2동주민센터"], "place_type": "공공기관", "road_only": false, "segment": false, "no_location": false, "outside_seongnam": false, "reason": "동사무소는 현재 행정복지센터"}"""


def _prompt(raw: str, gu: str | None, context: str) -> str:
    return (f"자료 종류: {context}\n"
            f"구: {gu or '모름'} (성남시)\n"
            f"원래 글자: {raw}\n"
            "이 글자를 다듬어 JSON으로 답해라.")


# 프롬프트에 들어간 자료 ID (대장 06). 배치가 자료에 맞게 정한다: 단속 DAT-05, 신호기 DAT-13, 민원 DAT-64 …
DATA_IDS: list[str] = []
_cfg = task_config(C.LLM_TASK)
LLM_MODEL = (_cfg.model if _cfg else "") or "exaone3.5:7.8b"     # 캐시 열쇠 (예전 캐시와 같게)
last_error: str | None = None


def _call(user: str) -> str | None:
    """공통 LLM 모듈로 부른다 (W05-05). 내부·외부 판단과 로그는 공통 모듈이 한다."""
    global last_error
    r = call_llm(C.LLM_TASK, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                 data_ids=DATA_IDS, contains_raw=False, response_format="json")
    last_error = None if r.ok else r.error_code
    return r.text if r.ok else None


def refine(raw: str, gu: str | None, context: str) -> dict | None:
    if not C.LLM_ENABLED:
        return None
    key = f"{LLM_MODEL}|{context}|{gu}|{raw}"
    if key in _cache:
        text = _cache[key]
    else:
        text = _call(_prompt(raw, gu, context))
        if text is None:                      # 실패는 캐시에 남기지 않는다 (Ollama가 꺼졌을 때 등)
            return None
        _cache[key] = text
    text = re.sub(r"//[^\n]*", "", text or "")   # 주석 섞인 응답 대비
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    # 안전장치: 숫자 좌표처럼 보이는 검색어는 버린다
    out["queries"] = [q for q in out.get("queries", [])[:3]
                      if isinstance(q, str) and q.strip() and not re.search(r"\d{2,3}\.\d{3,}", q)]
    return out


def check_policy(dataset: str, data_ids: list[str]) -> None:
    """배치 시작 때 부른다. 프롬프트에 들어갈 자료 ID를 정한다 (외부 전송 판단은 공통 모듈이 강제, POL-021)."""
    global DATA_IDS
    DATA_IDS = list(data_ids)
    route = f"{_cfg.route} ({_cfg.model})" if _cfg else "작업 설정 없음"
    print(f"[POL-021] {dataset}: LLM {'꺼짐' if not C.LLM_ENABLED else route} · 자료 {','.join(DATA_IDS) or '-'}")
