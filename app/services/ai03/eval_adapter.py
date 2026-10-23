"""AI-03 평가 어댑터 (W05-06 공통 평가 틀용).

입력 한 줄: "자료종류 | 구 | 위치 글자"  (구가 없으면 비움: "장소 |  | ○○공원")
  자료종류: 교차로(경찰 신호·신호기 교차로명) / 장소(단속장소) / 주소(신호기 설치주소) / 민원
돌려주는 값
  run(입력)          → gid (좌표를 내지 않으면 None)
  run_status(입력)   → 상태 (성공 / 못 찾음 / 도로 단위 / 구간 / 성남 밖 / 위치 없음 / 이름 모호)
  run_accuracy(입력) → coord_accuracy ('보통' / '낮음', 좌표를 내지 않으면 None)

규칙 (AI-03이 DB에 반영하는 기준과 같음)
  - '반영 보류'(신뢰도 낮음 등 사람 확인 전)는 좌표를 내지 않은 것으로 본다 → gid None, 상태 '못 찾음'
  - 검증에서 떨어진 것(이름 불일치·단서 불일치·구 불일치·격자 밖 등)도 '못 찾음'
  - coord_accuracy: 주소 검색으로 찾으면 '보통', 장소 검색·내부 대조는 '낮음' (A-06 적용 전 값)
  - 상태 이름을 영어 코드로 바꾸더라도 여기서 한글로 바꿔 돌려준다 (정답 파일은 그대로)
같은 입력은 한 번만 계산한다 (세 함수가 같은 결과를 나눠 씀).
"""
from functools import lru_cache

from app.services.ai03 import pipeline

KEEP = {"성공", "못 찾음", "도로 단위", "구간", "성남 밖", "위치 없음", "이름 모호"}
EN2KO = {"found": "성공", "not_found": "못 찾음", "road_only": "도로 단위", "segment": "구간",
         "outside": "성남 밖", "no_location": "위치 없음", "ambiguous": "이름 모호"}
CONTEXT = {"교차로": "교통신호기 교차로명", "장소": "주정차 단속장소", "민원": "보행안전 민원 신고 위치"}


def _parse(line: str):
    parts = [p.strip() for p in str(line).split("|")]
    while len(parts) < 3:
        parts.insert(1, "")
    kind, gu, text = parts[0], parts[1] or None, "|".join(parts[2:]).strip()
    return kind, gu, text


@lru_cache(maxsize=None)
def _result(line: str) -> dict:
    kind, gu, text = _parse(line)
    if kind == "주소":
        r = pipeline.by_address(text, gu) or {"상태": "못 찾음"}
    elif kind == "교차로":
        r = pipeline.process(text, gu, CONTEXT["교차로"], profile="교차로")
    else:
        r = pipeline.process_place(text, gu, CONTEXT.get(kind, CONTEXT["장소"]))
    status = EN2KO.get(r.get("상태"), r.get("상태"))
    held = r.get("단서일치") is False or r.get("신뢰도") == "낮음"          # 반영 보류
    out = status == "성공" and not held and r.get("gid")
    api = str(r.get("사용_API") or "")
    return {
        "gid": r.get("gid") if out else None,
        "status": "성공" if out else (status if status in KEEP and status != "성공" else "못 찾음"),
        "accuracy": (("보통" if ("주소" in api and "장소" not in api) or r.get("단계") == "규칙+주소검색" else "낮음")
                     if out else None),
    }


def run(line: str):
    return _result(line)["gid"]


def run_status(line: str) -> str:
    return _result(line)["status"]


def run_accuracy(line: str):
    return _result(line)["accuracy"]
