"""AI-01 가린 요약 (7단계) + 요약 검사 (7-1단계).

가린 글을 공통 LLM 모듈(작업 ai01_summarize, 내부 모델)로 두 문장 이하로 줄인다.
장소 표현은 남기고, 남은 개인정보는 쓰지 않게 한다. 요약에 꼴이 남으면 규칙으로 한 번 더 가린다.
- 이미 짧은 글(200자 이하)은 모델을 부르지 않고 가린 글을 그대로 쓴다 (빠르고, 지어낼 일이 없다)
- 요약에 가린 글에 없는 장소가 나오면(모델이 지어냄) 요약을 버리고 가린 글 앞부분을 쓴다 (12단계 위치 대조)
"""
from __future__ import annotations

import re

from app.core.llm import call_llm
from app.services.ai01 import masking

MAX_INPUT = 3000
SHORT = 200
VERSION = "sum-3"
_RESTATE = re.compile(r"^.{0,40}(?:불법\s*주정차|불법\s*주차)\s*신고입니다\.?$")
RULE_HEAD = 150
PLACE = re.compile(r"[가-힣0-9]{2,}(?:시|구|동|로|길|역|학교|아파트|공원|정류장|정류소|사거리|삼거리|교차로|센터|병원|시장|마을|단지)(?![가-힣])")

SYSTEM = """너는 성남시 보행안전 민원을 정리하는 도우미다. 입력은 개인정보를 일부 가린 민원 글이다.
규칙:
1. 민원 내용을 두 문장 이하, 150자 안팎으로 줄인다. 무엇이 어디에서 문제인지, 왜 요청하는지(배경)가 드러나게 쓴다.
2. 장소 표현(주소, 도로명, 동 이름, 건물·아파트·학교·기관·정류장 이름, 교차로, 역 이름)은 원문 그대로 남긴다. 장소가 여러 곳이면 모두 쓴다.
3. 사람 이름, 전화번호, 차량번호(버스·이륜차 번호판 포함), 접수번호, 동·호수, 생년월일·출생 연도, 나이, 성별, 이메일, 다친 곳·병명은 쓰지 않는다.
4. [이름], [전화], [차량번호] 같은 대괄호 표시는 요약에 넣지 않는다.
5. 원문에 없는 내용을 지어내지 않는다. 판단이나 의견을 더하지 않는다.
답은 JSON 하나로만 한다: {"summary": "요약 문장"}"""


def _clean(text: str) -> str:
    text = re.sub(r"\[[가-힣A-Za-z0-9]+\]\s?", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _head(text: str, n: int = SHORT) -> str:
    """가린 글 앞부분을 문장 끝에서 자른다."""
    t = _clean(text)
    if len(t) <= n:
        return t
    cut = max(t.rfind(". ", 0, n), t.rfind("다. ", 0, n))
    return t[: cut + 1] if cut > 50 else t[:n] + "…"


def rule_summary(report_type: str, masked_text: str) -> str:
    """신고 분류로 관련 여부가 정해진 민원(대부분 안전신문고)은 모델 없이 '신고 분류 · 본문 앞부분'으로 요약한다 (AI01-D06)."""
    body = masked_text.split("\n", 1)[1] if "\n" in masked_text else ""     # 첫 줄(제목)은 신고 분류와 겹친다
    lines = [x for x in body.splitlines() if not _RESTATE.match(x.strip())]   # "○○ 불법 주정차 신고입니다." 같은 되풀이 줄
    head = _head("\n".join(lines), RULE_HEAD)
    return f"{report_type} · {head}" if head else report_type


def made_up_places(summary: str, masked_text: str) -> list:
    src = re.sub(r"\s", "", masked_text)
    return [p for p in PLACE.findall(summary) if re.sub(r"\s", "", p) not in src]


def summarize(masked_text: str, request_id: str | None = None) -> tuple[str | None, list]:
    """(요약, 검사에 걸린 것 목록). 모델 호출이 실패하면 (None, [])."""
    if len(_clean(masked_text)) <= SHORT:
        return _head(masked_text), []
    r = call_llm("ai01_summarize",
                 [{"role": "system", "content": SYSTEM}, {"role": "user", "content": masked_text[:MAX_INPUT]}],
                 contains_raw=False, response_format="json", request_id=request_id)
    if not r.ok or not isinstance(r.data, dict):
        return None, []
    summary = str(r.data.get("summary", "")).strip()
    if not summary:
        return None, []
    if made_up_places(summary, masked_text):
        return _head(masked_text), ["지어낸 장소"]
    hits = masking.left_kinds(summary) + (["의심"] if masking.SUSPECT.search(summary) else [])
    if hits:
        import collections
        summary = masking.rule_mask(summary, collections.Counter())
    summary = _clean(summary)
    return summary or None, hits
