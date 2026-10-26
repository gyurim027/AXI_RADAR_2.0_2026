"""1단계: AI 없이 규칙으로 정리·분류 (기준선 겸 LLM 호출 줄이기)."""
import re

# 위치가 아닌 값(원본 표 머리글 등)
NOT_LOCATION = {"제어기설치년도", "설치년도", "비고", "기타", "위반장소", "한가운데", "도로한가운데", "도로주행"}

# 브랜드만 남으면 성남 안에 같은 이름이 여러 곳 → 내부 대조 금지, AI·브이월드로 넘김
GENERIC = {"이마트", "이마트24", "홈플러스", "롯데마트", "베스킨라빈스", "양평해장국", "맥도날드", "버거킹", "투썸플레이스", "메가커피", "빽다방",
           "청소년수련관", "톨게이트", "공용주차장", "주차장", "성남농협", "농협성남지점", "행정복지센터", "주민센터", "동행정복지센터", "우리은행", "국민은행", "신한은행", "하나은행", "기업은행", "농협", "농협은행", "새마을금고", "우체국", "스타벅스", "이디야", "파리바게뜨", "올리브영", "다이소", "kt", "KT", "세븐일레븐", "GS25", "CU", "주택단지", "빌라단지", "상가", "시장", "편의점", "약국", "e편한세상", "하늘채", "데시앙", "래미안", "래미안아파트", "자이", "자이아파트",
           "힐스테이트", "현대아파트", "아파트", "보육시설", "공영주차장", "주유소", "교회", "시청",
           "천주교성당", "성당", "탄천", "우체국", "어린이집", "유치원", "공원", "주차장", "정류장"}

# 교차로·위치 꼬리말 (뒤에서 떼어냄)
SUFFIX = r"(오거리|사거리|삼거리|교차로|단일로|입구부근|출구부근|입구|정문|후문|서문|동문|남문|북문|출구|앞|뒤|옆|밑|아래|건너편|맞은편|주변|부근|인근|근처)$"

# 약칭 → 정식 이름 (순서 중요: 긴 것 먼저)
ABBR = [
    (r"여중고$", "여자중학교"),
    (r"중고$", "중학교"),
    (r"여고$", "여자고등학교"),
    (r"초교$", "초등학교"),
    (r"중교$", "중학교"),
    (r"고교$", "고등학교"),
    (r"초$", "초등학교"),
    (r"중$", "중학교"),
    (r"고$", "고등학교"),
    (r"동사무소$", "동행정복지센터"),
    (r"(주민센타|주민센터)$", "행정복지센터"),
    (r"센타$", "센터"),
]
BRAND = [(r"[Ee]편한세상", "e편한세상"), (r"힐스테이$", "힐스테이트")]

ROAD_RE = re.compile(r"^[가-힣0-9]+(대로|로|길)(\d+번?길)?$")
ROAD_ADDR_RE = re.compile(r"^([가-힣0-9]+(?:대로|로|길))\s*(\d+(?:-\d+)?)$")  # 광명로33 → 광명로 33
SEGMENT_RE = re.compile(r"(~|사이|구간)")


def compact(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def clean(raw: str) -> str:
    s = str(raw or "").strip()
    if re.fullmatch(r"\(.*\)", s):             # '(판교초교 공원앞)'처럼 전체가 괄호면 벗긴다
        s = s[1:-1]
    s = re.sub(r"\(.*?\)", " ", s)              # (S-10) 등 괄호 제거
    s = re.sub(r"\b\d+R\b", " ", s)             # 3R
    s = re.sub(r"\s*\d+$", "", s) if not ROAD_ADDR_RE.match(compact(s)) else s  # '단대쇼핑 1' → '단대쇼핑'
    s = re.sub(r"[\"'“”‘’.·]|㈜|\(주\)", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def core_name(s: str) -> str:
    """꼬리말·동 번호를 떼고 약칭을 정식 이름으로."""
    c = compact(s)
    for _ in range(2):
        c = re.sub(SUFFIX, "", c)
    c = re.sub(r"\d+동$", "", c)                 # 1301동, 113동
    c = re.sub(r"신호등\d*$", "", c)
    for pat, rep in BRAND:
        c = re.sub(pat, rep, c)
    for pat, rep in ABBR:
        if re.search(pat, c):
            if rep == "중학교" and re.search(r"(정차|주차|대기|운행|주행|공사|통행|진행|신호대기)중$", c):
                break                      # '갓길정차중'은 학교가 아니다
            if rep == "고등학교" and re.search(r"(금고|신고|광고|창고|차고|사고|재고|최고|경고|충전고)$", c):
                break                      # '새마을금고', '불법주차신고'는 학교가 아니다
            c = re.sub(pat, rep, c)
            break
    return c


def classify(raw: str) -> dict:
    """규칙으로 판정 가능한 것은 여기서 끝낸다."""
    s = clean(raw)
    c = compact(s)
    if not c or c in NOT_LOCATION:
        return {"status": "위치 없음", "query": None, "kind": None}
    if SEGMENT_RE.search(s):
        return {"status": "구간", "query": None, "kind": "도로"}
    m = ROAD_ADDR_RE.match(c)
    if m:
        return {"status": "후보", "query": f"{m.group(1)} {m.group(2)}", "kind": "도로명주소"}
    core = core_name(s)
    if not core:
        return {"status": "위치 없음", "query": None, "kind": None}
    if ROAD_RE.match(core):
        return {"status": "도로 단위", "query": core, "kind": "도로"}
    if core in GENERIC:
        return {"status": "이름 모호", "query": core, "kind": "장소"}
    return {"status": "후보", "query": core, "kind": "장소"}


# AI 검색어 후처리: 작은 모델이 붙이는 군더더기(구 이름, '교차로', '보행신호', '부근')를 떼고,
# 원래 글자와 너무 달라진 검색어(지어낸 이름)는 버린다.
NOISE_RE = re.compile(r"(경기도|성남시|수정구|중원구|분당구|보행신호|교통신호|신호|교차로|주정차|단속장소|단속|부근|주변|인근|근처|일대|출입구|구간)")


def sanitize_query(q: str, raw: str) -> str | None:
    q2 = NOISE_RE.sub(" ", str(q or ""))
    q2 = core_name(clean(q2))
    q2 = re.sub(r"^[가-힣0-9]+?(대로|로|길)\d*(번?길)?(?=[가-힣A-Za-z]{2,})", "", q2)   # 앞에 붙은 도로명 떼기
    if re.match(r"^[가-힣]+\d?동$", q2):          # 동 이름만 남으면 위치가 아님 (중앙동 → 중앙동사거리 오연결 방지)
        return None
    m = re.match(r"^[가-힣]+\d?동(.{3,})$", q2)      # 앞에 붙은 동 이름 떼기 (수내동돌고래재래시장 → 돌고래재래시장)
    if m and not re.match(r"^(행정복지센터|주민센터|우체국|파출소|지구대)", m.group(1)):
        q2 = m.group(1)
    if len(q2) < 3 or q2 in GENERIC or q2 in {"우체국", "아파트단지", "현대아파트단지"}:
        return None
    # 원문 핵심과 글자가 절반 이상 겹쳐야 인정 (예: 성남동현대아파트 → 현대아파트 는 통과, 중원보건소 → 보건센터 는 탈락)
    base = core_name(clean(raw))
    a = {base[i:i+2] for i in range(len(base)-1)}
    b = {q2[i:i+2] for i in range(len(q2)-1)}
    if a and len(a & b) / len(b or {1}) < 0.5:
        return None
    # 원문 번호(판교테크노13, 55단지, 2번출구)가 검색어에서 사라지면 다른 곳을 찾게 된다
    nums = re.findall(r"\d+", base)
    if nums and not all(n in q2 for n in nums):
        return None
    # 원문에 없던 도로 이름으로 바뀐 경우(금광주유소 → 금광로)는 도로 위 임의 점이 되므로 버린다
    if ROAD_RE.match(q2) and not ROAD_RE.match(base):
        return None
    return q2


# 이름이 바뀐 시설: 브이월드에서 못 찾으면 바뀐 이름으로 한 번 더 찾는다
SYNONYM = [(r"지구대$", "파출소"), (r"파출소$", "지구대"),
           (r"행정복지센터$", "주민센터"), (r"보건소$", "보건센터")]
# 자주 옮기거나 이름이 바뀌는 시설 → 이름이 맞아도 신뢰도 한 단계 낮춤
VOLATILE_RE = re.compile(r"(지구대|파출소|치안센터|공판장|견인소|임시)")


def synonyms(q: str) -> list[str]:
    out = []
    for pat, rep in SYNONYM:
        if re.search(pat, q):
            out.append(re.sub(pat, rep, q))
    return out


# ---- 단속장소·민원처럼 '동 + 도로 + 랜드마크 + 주변' 형태 쪼개기 ----
DONG_TOK = re.compile(r"^[가-힣]+\d?동$")
ROAD_TOK = re.compile(r"^[가-힣0-9]+(대로|로|길)(\d+번?길)?$")
PARCEL_RE = re.compile(r"([가-힣]+\d?동)\s*(산?\d+(?:-\d+)?)\s*(번지)?$")
FILLER_TOK = {"주변", "부근", "인근", "근처", "일대", "앞", "뒤", "옆", "맞은편", "건너편", "입구", "입구부근", "출구부근", "안전지대",
              "횡단보도", "인도", "보도", "차도", "도로", "도로변", "갓길", "교차로", "사거리", "삼거리", "현관", "쪽", "방향", "위", "밑", "아래"}
OUTSIDE_RE = re.compile(r"(서울특별시|서울시|서울\s?[가-힣]+구|강남구|송파구|서초구|동작구|관악구|반포|구로|용인시|수지구|기흥구|광주시|하남|과천|의왕|수원|안양|남양주|구리시|"
                        r"인천|부천|화성시|천안|공주시|의정부|이천시|충남|충북|전남|전북|경북|경남|강원|부산|대구|대전|울산|세종|제주)")
# '분당서울대병원', '서울방면', '서울산전'처럼 서울이 들어가도 성남 안인 경우
INSIDE_HINT_RE = re.compile(r"(분당서울대|서울대병원|서울방면|서울방향|서울산전)")
HIGHWAY_RE = re.compile(r"(고속도로|고속화도로|순환고속|외곽순환)")


def parse_parts(raw: str) -> dict:
    """'성남동 광명로 광명인쇄사 주변' → {dong:성남동, road:광명로, landmark:광명인쇄사}"""
    raw0 = re.sub(r"\(.*?\)", " ", str(raw or "")).strip()
    m = PARCEL_RE.search(raw0)          # 지번은 clean() 전에 확인 (끝 숫자가 지워지지 않게)
    s = clean(raw)
    s = re.sub(r"[.,]", " ", s)
    s = s.replace("섬남", "성남").replace("성남싱", "성남시")
    s = re.sub(r"지하\s?\d+층|\d+층|[가-힣]+(방면|방향)|\d+차로|\d+차선", " ", s)   # 층·방향·차로는 위치 이름이 아님
    s = re.sub(r"(^|\s)(경기도|경기|성남시|성남|수정구|중원구|분당구)(?=\s|$)", " ", s).strip()   # 시·구 이름은 위치 이름이 아님
    if m:
        return {"dong": m.group(1), "road": None, "landmark": None, "parcel": f"{m.group(1)} {m.group(2)}"}
    dong = road = None
    rest = []
    for tok in s.split():
        if dong is None and DONG_TOK.match(tok) and not rest:
            dong = tok
        elif road is None and ROAD_TOK.match(tok):
            road = tok
        elif tok not in FILLER_TOK:
            rest.append(tok)
    # 붙여 쓴 '판교로256번길환상어린이공원' 같은 경우: 앞쪽 도로 이름 떼기
    if road is None and rest:
        m2 = re.match(r"^([가-힣0-9]+?(?:대로|로|길)\d*(?:번?길)?)(.+)$", rest[0])
        if m2 and len(m2.group(2)) >= 2 and not re.match(r"^\d", m2.group(2)):
            road, rest[0] = m2.group(1), m2.group(2)
    landmark = core_name("".join(rest)) if rest else None
    # '구미1동 행정복지센터'처럼 동 이름이 있어야 특정되는 기관은 동을 붙인다
    if landmark and dong and re.match(r"^(\d+단지|\d+차|행정복지센터|주민센터|동행정복지센터|우체국|파출소|지구대|도서관|경로당|어린이집|보건지소)", landmark):
        landmark = dong + landmark.replace("동행정복지센터", "행정복지센터")
    return {"dong": dong, "road": road, "landmark": landmark or None, "parcel": None}


def classify_place(raw: str) -> dict:
    """단속장소·민원용 분류. 단서(동·도로)는 검증에 쓴다."""
    c = compact(clean(raw))
    if not c or c in NOT_LOCATION:
        return {"status": "위치 없음", "query": None, "kind": None, "hint": {}}
    if SEGMENT_RE.search(raw or ""):
        return {"status": "구간", "query": None, "kind": "도로", "hint": {}}
    if HIGHWAY_RE.search(raw or ""):                     # 고속도로는 성남 안팎과 상관없이 도로 단위
        return {"status": "도로 단위", "query": None, "kind": "도로", "hint": {}}
    raw_chk = INSIDE_HINT_RE.sub(" ", str(raw or ""))
    if OUTSIDE_RE.search(raw_chk) and "성남" not in raw_chk:
        return {"status": "성남 밖", "query": None, "kind": None, "hint": {}}
    p = parse_parts(raw)
    hint = {"dong": p["dong"], "road": p["road"]}
    if p["parcel"]:
        return {"status": "후보", "query": p["parcel"], "kind": "지번주소", "hint": hint}
    lm = p["landmark"]
    if lm and re.fullmatch(r"(" + "|".join(sorted(FILLER_TOK, key=len, reverse=True)) + r")+", lm):
        lm = None                          # '인도위'처럼 위치 설명어만 붙은 것
    if lm and not re.search(r"[가-힣A-Za-z]{2,}", re.sub(r"\d+동", "", lm)):
        lm = None                          # '1동현관'처럼 이름이 없는 것
    if not lm or len(lm) < 2:
        if p["road"]:
            return {"status": "도로 단위", "query": p["road"], "kind": "도로", "hint": hint}
        return {"status": "위치 없음", "query": None, "kind": None, "hint": hint}
    if re.fullmatch(r"[가-힣]+\d?동", lm):
        return {"status": "이름 모호", "query": lm, "kind": "장소", "hint": hint}   # '고등동사거리' → 동 이름만으로는 지점을 못 정함
    if lm in GENERIC or len(lm) <= 2:
        # 흔한 이름: 도로·동 단서가 있으면 그 단서와 맞는 후보만 받는다
        if p["road"] or p["dong"]:
            return {"status": "후보", "query": lm, "kind": "장소", "hint": {**hint, "필수": True}}
        return {"status": "이름 모호", "query": lm, "kind": "장소", "hint": hint}
    return {"status": "후보", "query": lm, "kind": "장소", "hint": hint}


# 브이월드가 정식 이름과 조금만 달라도 못 찾으므로, 꾸밈말을 뺀 짧은 이름으로 다시 찾는다
SHORTEN = ["재래", "환승", "공영", "제\\d+", "장애인주차장", "주차장", "\\d+동", "오피스텔", "빌딩", "센터", "아파트", "단지", "타워", "시티", "프라자", "플라자"]


REGION_PREFIX = re.compile(r"^(판교|위례|야탑|서현|정자|분당|수내|미금|오리|모란|태평|신흥|단대|금광|상대원|도촌|여수|은행|이매|백현|삼평|운중|대장|고등|복정|창곡)(?=[가-힣A-Za-z]{2,})")


def variants(q: str) -> list[str]:
    if not q or len(q) < 5:
        return []
    out = []
    m = REGION_PREFIX.match(q)
    if m:
        out.append(q[m.end():])            # 판교투썬월드빌딩 → 투썬월드빌딩
    for w in SHORTEN:
        v = re.sub(w, "", q)
        if v != q and len(v) >= 3:
            out.append(v)
    allv = q
    for w in SHORTEN[:4]:
        allv = re.sub(w, "", allv)
    if allv != q and len(allv) >= 3:
        out.append(allv)
    seen, res = set(), []
    for v in out:
        head = re.sub(r"(주차장|시장|병원|교회|학교|공원|아파트|센터|은행|마트|상가|빌라|약국)$", "", v)
        if len(head) < 3:                 # '야탑주차장'처럼 너무 일반적인 이름은 다른 곳을 잡는다
            continue
        if v not in seen and v not in GENERIC:
            seen.add(v); res.append(v)
    return res[:4]



def road_stem(road: str | None) -> str | None:
    """판교역로10번길 → 판교역, 하오개로391번길 → 하오개, 산성대로 → 산성"""
    if not road:
        return None
    return re.sub(r"(대로|로|길)(\d+번?길)?$", "", compact(road)) or None



# ---- 설치주소 정리: '광명로395번길7', '경기도 성남시 수정구 성남시 수정구 단대동 108-8 일원' 등 ----
_ADDR_ROAD = re.compile(r"([가-힣0-9]+(?:대로|로|길)(?:\d+번?길)?)\s*(\d+(?:-\d+)?)(?!\d)")
_ADDR_PARCEL = re.compile(r"([가-힣]+\d?(?:동|리))\s*(산\s?\d+(?:-\d+)?|\d+(?:-\d+)?)(?!\d)")


def clean_address(addr: str, gu: str | None) -> list[tuple[str, str]]:
    """설치주소 → [(검색할 주소, 'ROAD'|'PARCEL')]. 도로명주소를 먼저, 지번을 다음으로."""
    if not addr or str(addr).strip() in ("", "nan"):
        return []
    a = re.sub(r"\(.*?\)", " ", str(addr))
    a = re.sub(r"(경기도|경기|성남시|수정구|중원구|분당구)", " ", a)
    out = []
    m = _ADDR_ROAD.search(a)
    if m:
        out.append((f"경기도 성남시 {gu or ''} {m.group(1)} {m.group(2)}".replace("  ", " "), "ROAD"))
    m = _ADDR_PARCEL.search(a)
    if m:
        out.append((f"경기도 성남시 {gu or ''} {m.group(1)} {m.group(2).replace(' ', '')}".replace("  ", " "), "PARCEL"))
    return out


def road_hint_from(text: str | None) -> str | None:
    """'도로명_또는_위치' 칸이 진짜 도로 이름일 때만 단서로 쓴다 (서판교·기타(경보등)·23호 국지도 제외)."""
    t = compact(str(text or ""))
    return t if ROAD_TOK.match(t) else None
