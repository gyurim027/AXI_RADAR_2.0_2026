"""AI-01 개인정보 가림 (C-03).

순서: 전처리(꼬리표·틀 문구 빼기) → 넓은 규칙 → 이름 찾기 모델(koelectra-ko-pii-ner) → 가림 검사.
- 원문은 이 함수 안 메모리에서만 쓴다. 원문을 돌려주거나 로그에 남기지 않는다 (ISS-032, POL-008).
- 장소 표현(주소·도로명·건물·기관·정류장 이름)은 남긴다. 위치 글자 다듬기(AI-03)가 가린 글에서 위치를 찾는다.
- 이름 모델이 일반 낱말을 이름으로 잘못 보는 것을 막으려고 '흔한 낱말 목록'에 있는 낱말은 가리지 않는다.
  목록은 민원에서 만든 것이라 저장소에 두지 않는다. 경로는 .env의 AI01_COMMON_WORDS (scripts/ai01_build_common_words.py로 만듦).
"""
from __future__ import annotations

import collections
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("radar.ai01")
NER_MODEL = "atonlee/koelectra-ko-pii-ner"
VERSION = "mask-1"

PLATE = "[가나다라마바사아자차카타파하거너더러머버서어저고노도로모보소오조구누두루무부수우주허호배육해공국합]"   # 번호판에 쓰는 글자
REGION = "서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주"
PLATE_CUE = r"(?:이륜차|오토바이|번호판|차량번호|차번|버스|차량|택시|트럭|화물차|승용차)"
TITLES = r"(?:국회의원|시의원|구의원|도의원|의원|위원장|팀장|과장|계장|주임|국장|실장|소장|반장|선생님|주무관)"

# (자리표시, 꼴). 위에서부터 차례로 바꾼다. 꼴에 lead 묶음이 있으면 그 앞말은 남긴다.
_RULES = [
    ("[주민번호]", r"(?<![\d.])\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-?[1-4]\d{6}(?![\d.])"),
    ("[외국인번호]", r"(?<![\d.])\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-?[5-8]\d{6}(?![\d.])"),
    ("[운전면허]", r"(?<!\d)\d{2}-\d{2}-\d{6}-\d{2}(?!\d)"),
    ("[여권]", r"(?<![A-Za-z0-9])[MSRODG]\d{8}(?![0-9])"),
    ("[계좌]", r"(?<=은행|계좌)[^\n]{0,15}?\d{2,6}-\d{2,6}-\d{2,7}"),
    ("[접수번호]", r"(?<![\w-])[0-9A-Z]{1,4}-\d{4}-[0-9A-Z]{5,10}(?![\w-])"),
    ("[휴대전화]", r"(?<![\d.])01[016789][-.\s)]{0,2}\d{3,4}[-.\s]{0,2}\d{4}(?!\d)(?!\.\d)"),
    ("[전화]", r"(?<![\d.])\(?0(?:2|3[1-3]|4[1-4]|5[1-5]|6[1-4]|70|50\d)\)?[-.\s)]{0,2}\d{3,4}[-.\s]{0,2}\d{4}(?!\d)(?!\.\d)"),
    ("[전화]", r"(?<![\d.\-])1[568]\d{2}[-.\s]?\d{4}(?![\d.\-])"),
    ("[전화]", r"(?P<lead>(?:번호|핸드폰|휴대폰|연락처|전화|☎|[Tt][Ee][Ll])[^\n\d]{0,10}?)(?<!\d)\d[\d`'´]{1,3}[\s.\-`)]{1,2}\d{3,4}[\s.\-]{1,2}\d{4}(?!\d)"),
    ("[전화]", r"(?<![\d.\-])\d{3}-\d{3,4}-\d{4}(?![\d\-])"),
    ("[전화]", r"(?<![\d.\-])(?!(?:19|20)\d{2}-(?:19|20)\d{2})\d{3,4}-\d{4}(?![\d.\-])"),
    ("[메일]", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("[IP]", r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])"),
    ("[동호수]", r"\d{1,4}\s?동\s?\d{1,4}\s?호"),
    ("[차량번호]", r"(?:" + REGION + r")\s?[\(\[]\s?" + PLATE + r"\s?[\)\]]\s?\d{4}(?!\d)"),
    ("[차량번호]", r"(?P<lead>[\(\[]\s?)" + PLATE + r"\s?\d{4}(?!\d)"),
    ("[차량번호]", r"(?<![가-힣\d])" + PLATE + r"\s?\d{4}(?=\s?번(?![지길]))"),
    ("[차량번호]", r"(?:" + REGION + r")\s?[가-힣]{0,3}\s?" + PLATE + r"\s?\d{4}(?!\d)"),
    ("[차량번호]", r"(?P<lead>" + PLATE_CUE + r"[^\n]{0,15}?)(?<![가-힣\d])" + PLATE + r"\s?\d{4}(?!\d)"),
    ("[차량번호]", r"(?P<lead>(?:차량번호|차번|차량\s?번호|번호판|버스\s?번호)\s*[:：]?\s*)(?<!\d)\d{4}(?!\d)(?!\s?(?:년|월|일|번길|길|호))"),
    ("[차량번호]", r"(?<!\d)\d{2,3}\s?" + PLATE + r"\s?\d{4}(?!\d)(?!\s?(?:번?길|호))"),
    ("[생년월일]", r"(?:생년월일|출생일)\s*[:：]?\s*[\d.\-/년월일\s]{6,14}|\d{2,4}\s?년생"
                  r"|(?:19|20)?\d{2}\s?[년.\-/]\s?\d{1,2}\s?[월.\-/]\s?\d{1,2}\s?일?\s?(?:생|출생)(?![가-힣])"),
    ("[이름]", r"(?P<lead>(?<!정류장 )(?<!정류소 )(?<!정류장)(?<!정류소)(?<!건물 )(?<!업체 )(?<!상호 )(?<!학교 )(?<!단지 )(?<!공원 )(?<!도로 )"
               r"(?:성명|이름|신고인|민원인|고발인|작성자)\s*[:：]\s*)[가-힣]{2,4}"),
    ("[이름]", r"(?P<lead>\[이름\]\s?[,，·]\s?)[가-힣]{2,4}(?![가-힣])"),
    ("[이름]", r"(?P<lead>\[이름\]\s?[,，·]\s?)[가-힣]{2,4}(?![가-힣])"),
    ("[이름]", r"(?<![가-힣])(?!(?:교장|교감|담임|담당|해당|관계|현장|센터|지역|구의|시의|도의|국회|부서|업무|우리|저희|그|이)\s)"
               r"[가-힣]{1,2}[가-힣](?<![시군구읍면청회과팀국단])(?=\s" + TITLES + ")"),
    ("[공무원]", r"[가-힣]{2,4}\s?(?:경위|경사|경장|순경|경감|주무관)|(?:경위|경사|경장|순경|경감|주무관)\s?[가-힣]{2,4}(?=\s?\()"),
    ("[나이]", r"(?<!\d)\d{1,2}\s?(?:세|살)(?![가-힣])"),
    ("[성별]", r"남성|여성|남자|여자"),
    ("[건강정보]", r"(?:제가|저는|본인은|본인이|아이가|어머니가|아버지가|부모님이)[^\n]{0,15}?(?:질병|질환|수술|임신|환자|병원)"),
]
RULES = [(tag, re.compile(p)) for tag, p in _RULES]
HOME = [(re.compile(r"(?:우리|저희)\s?(?:집|아파트)"), "주택가"), (re.compile(r"자택"), "주택가")]

# 가린 뒤 남으면 '가림 실패'인 꼴 (적재 검사 6번의 3꼴 + 추가)
CHECK = {
    "차량번호": re.compile(r"(?<!\d)\d{2,3}\s?" + PLATE + r"\s?\d{4}(?!\d)(?!\s?(?:번?길|호))"),
    "휴대전화": RULES[6][1],
    "메일": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "일반전화": RULES[7][1],
    "주민번호": RULES[0][1],
    "번호판4자리": re.compile(r"(?:차량번호|차번|차량\s?번호|번호판|버스\s?번호)\s*[:：]?\s*(?<!\d)\d{4}(?!\d)(?!\s?(?:년|월|일|번길|길|호))"),
    "생년월일": re.compile(r"(?:19|20)?\d{2}\s?[년.\-/]\s?\d{1,2}\s?[월.\-/]\s?\d{1,2}\s?일?\s?(?:생|출생)(?![가-힣])|(?:19|20)\d{2}\s?년생"),
    "접수번호": re.compile(r"(?<![\w-])[0-9A-Z]{1,4}-\d{4}-[0-9A-Z]{5,10}(?![\w-])"),
}
# 가림 의심: 실패로 빼지는 않고 세기만 한다 (사진 촬영 날짜 같은 숫자가 걸릴 수 있음)
SUSPECT = re.compile(r"(?<!\d)\d{9,11}(?!\d)|(?<!\d)\d{2,4}[\s.\-)]{1,2}\d{3,4}[\s.\-]{1,2}\d{4}(?!\d)")
PLACEHOLDER = re.compile(r"\[[가-힣A-Za-z]+\]")
LOC = re.compile(r"[가-힣]+동\s?\d{1,4}(?:-\d{1,4})?(?![\d가-힣])|[가-힣0-9]+(?:로|길)\s?\d{1,4}(?:-\d{1,3})?(?![\d가-힣])")
_TEMPLATE = re.compile(r"^\s*(?:\[|.*(?:위도|경도)\s*[:：]|\*?\s*\(\d+/\d+\)\s*[CGS]\s*:|\*\s*$|\*?\s*G\s*:|"
                       r".*안전신문고 신고파일|.*촬영시간 및 경로 안내|\*?\s*차량번호\s*:)")   # 안전신문고 앱이 붙이는 틀 줄


@dataclass
class MaskResult:
    ok: bool                                   # 가림 검사 통과
    text: str | None                           # 가린 글 (실패면 None)
    counts: dict = field(default_factory=dict) # 가린 종류별 개수
    left: list = field(default_factory=list)   # 실패 이유(남은 꼴 이름)
    suspect: int = 0
    location_lost: bool = False                # 위치 표현 개수가 줄었는지


TEMPLATE_MIN_SHARE = 0.3      # 한 업로드 파일 안 같은 출처 민원의 30% 넘게 똑같이 나오는 줄은 앱 안내 문구로 본다
TEMPLATE_MIN_COUNT = 20


def repeated_lines(bodies: list[str]) -> frozenset:
    """같은 파일 안에서 반복되는 줄(앱 안내 문구)을 찾는다. 메모리에서만 쓰고 저장하지 않는다."""
    if len(bodies) < TEMPLATE_MIN_COUNT:
        return frozenset()
    cnt = collections.Counter()
    for b in bodies:
        cnt.update({x.strip() for x in (b or "").splitlines() if x.strip()})
    need = max(TEMPLATE_MIN_COUNT, int(len(bodies) * TEMPLATE_MIN_SHARE))
    return frozenset(line for line, n in cnt.items() if n >= need)


def preprocess(title: str, body: str, drop: frozenset = frozenset()) -> str:
    """2단계 전처리: 제목 + 본문에서 꼬리표·좌표·촬영 시각 같은 틀 줄과, 파일 안에서 반복되는 안내 줄(drop)을 뺀다."""
    lines = [x for x in (body or "").splitlines()
             if x.strip() and not _TEMPLATE.match(x) and x.strip() not in drop]
    return (title or "").strip() + "\n" + "\n".join(lines)


def rule_mask(text: str, counts: collections.Counter) -> str:
    for tag, p in RULES:
        rep = (lambda m, t=tag: m.group("lead") + t) if "lead" in p.groupindex else tag
        text, n = p.subn(rep, text)
        if n:
            counts[tag.strip("[]")] += n
    for p, rep in HOME:
        text, n = p.subn(rep, text)
        if n:
            counts["거주표현"] += n
    return text


@lru_cache(maxsize=1)
def common_words() -> frozenset:
    path = os.environ.get("AI01_COMMON_WORDS", "")
    if not path or not Path(path).exists():
        logger.warning("ai01 흔한 낱말 목록이 없습니다(AI01_COMMON_WORDS). 이름 오탐이 늘 수 있습니다.")
        return frozenset()
    return frozenset(w.strip() for w in Path(path).read_text(encoding="utf-8").splitlines() if w.strip())


@lru_cache(maxsize=1)
def _ner():
    from transformers import pipeline                      # 선택 묶음 ai01 (torch, transformers)
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()
    return pipeline("token-classification", model=NER_MODEL, aggregation_strategy="simple",
                    device=os.environ.get("AI01_DEVICE", "cpu"))


def ner_mask(text: str, counts: collections.Counter, ner=None) -> str:
    """4-1·5단계: 400자 창(50자 겹침)으로 이름을 찾는다. 한글 2~4글자가 아니거나 흔한 낱말이면 가리지 않는다."""
    ner = ner or _ner()
    common = common_words()
    holders = [(m.start(), m.end()) for m in PLACEHOLDER.finditer(text)]
    spans = set()
    for start in range(0, max(len(text), 1), 400):
        seg = text[start:start + 450]
        if not seg.strip():
            continue
        for e in ner(seg):
            if e.get("entity_group") != "NAME" or e.get("score", 0) < 0.5:
                continue
            a, b = start + e["start"], start + e["end"]
            if any(s < b and a < t for s, t in holders):
                continue
            word = re.sub(r"\s", "", text[a:b])
            if not re.fullmatch(r"[가-힣]{2,4}", word) or word in common:
                counts["이름후보 거름"] += 1
                continue
            spans.add((a, b))
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    for a, b in reversed(merged):
        text = text[:a] + "[이름]" + text[b:]
    if merged:
        counts["이름(모델)"] += len(merged)
    return text


def left_kinds(text: str) -> list:
    return [k for k, p in CHECK.items() if p.search(text)]


def mask(title: str, body: str, ner=None, drop: frozenset = frozenset()) -> MaskResult:
    """한 민원을 가린다. 원문은 돌려주지 않는다."""
    raw = preprocess(title, body, drop)
    counts = collections.Counter()
    masked = ner_mask(rule_mask(raw, counts), counts, ner=ner)
    left = left_kinds(masked)
    lost = len(LOC.findall(masked)) < len(LOC.findall(raw))
    if left:
        return MaskResult(ok=False, text=None, counts=dict(counts), left=left, location_lost=lost)
    return MaskResult(ok=True, text=masked, counts=dict(counts), suspect=len(SUSPECT.findall(masked)), location_lost=lost)
