"""AI-03 공통 파이프라인 — 모든 테이블이 이 함수 하나를 쓴다.

순서: 규칙 정리 → 내부 자료 대조 → 브이월드(규칙 검색어) → [실패 시] LLM 다듬기 → 브이월드 → 검증 → gid
'단계' 칸으로 어디서 찾았는지 남겨, 발표 때 'AI 없이 ○건 → AI로 ○건 추가'를 바로 셀 수 있다.
"""
from . import rules
from . import internal_match
from . import llm
from . import validate
from .grid import to_gid

USE_VWORLD = True  # --offline 이면 False


def _try_vworld(query: str, kind: str, gu: str | None):
    from . import vworld
    cands = []
    if kind == "도로명주소":
        g = vworld.geocode(f"경기도 성남시 {gu or ''} {query}".replace("  ", " "), "ROAD")
        cands = [g] if g else []
        need_name = False
    else:
        cands = vworld.search_place(query)
        need_name = True
    last = "못 찾음"
    for c in cands:
        st, info = validate.check(c, query, gu, need_name=need_name)
        if st == "통과":
            return {**c, **info}, "통과"
        last = st
    return None, last


def _try_internal(core: str, gu: str | None):
    m = internal_match.match(core, gu)
    if not m or m.get("ambiguous"):
        return None
    gid, dist = to_gid(m["lat"], m["lon"])
    if gid is None:
        return None
    return {"lat": m["lat"], "lon": m["lon"], "gid": gid, "격자거리m": dist,
            "title": m["matched"], "api": f"내부 대조({m['source']})"}


def process(raw: str, gu: str | None, context: str, profile: str = "일반") -> dict:
    row = {"원문": raw, "구_기대": gu, "단계": None, "상태": None, "검색어": None,
           "장소_종류": None, "결과_이름": None, "사용_API": None,
           "위도": None, "경도": None, "gid": None, "AI_설명": None,
           "이름점수": None, "신호거리m": None, "신뢰도": None}

    # 1) 규칙
    r = rules.classify(raw)
    row["검색어"], row["장소_종류"] = r["query"], r["kind"]
    if r["status"] in ("위치 없음", "구간", "도로 단위"):
        row.update(단계="규칙", 상태=r["status"])
        return row

    def _fill(hit, stage):
        api = hit.get("api") or ""
        row.update(단계=stage, 상태="성공", 위도=round(hit["lat"], 6), 경도=round(hit["lon"], 6),
                   gid=hit["gid"], 결과_이름=hit.get("title"), 사용_API=api)
        g_stage = stage + ("·주소" if api.startswith("주소") else "")
        row.update(validate.grade(g_stage, row["검색어"], hit.get("title"), hit["lat"], hit["lon"], profile))
        return row

    ambiguous = r["status"] == "이름 모호"
    # 2) 내부 자료 대조 (API 없음)
    hit = None if ambiguous else _try_internal(r["query"], gu)
    if hit:
        return _fill(hit, "규칙+내부대조")

    # 3) 브이월드 — 규칙 검색어 그대로 (= AI 없는 기준선)
    last = "이름 모호" if ambiguous else "못 찾음"
    if USE_VWORLD and not ambiguous:
        hit, last = _try_vworld(r["query"], r["kind"], gu)
        if hit:
            return _fill(hit, "규칙+브이월드")
        for alt in rules.synonyms(r["query"]):      # 지구대 ↔ 파출소 등
            hit, _ = _try_vworld(alt, "장소", gu)
            if hit:
                row["검색어"] = alt
                return _fill(hit, "규칙+브이월드")

    # 4) LLM 다듬기 → 다시 내부 대조/브이월드
    ai = llm.refine(raw, gu, context) if r["kind"] != "도로명주소" else None
    flag_status = None
    if ai:
        qs = [rules.sanitize_query(q, raw) for q in ai["queries"]]
        ai["queries"] = [q for i, q in enumerate(qs) if q and q not in qs[:i] and q != r["query"]]
    if ai:
        row["AI_설명"] = ai.get("reason")
        row["장소_종류"] = ai.get("place_type") or row["장소_종류"]
        # 작은 모델은 판정 칸을 쉽게 true로 찍는다 → 검색어가 있으면 먼저 찾아보고,
        # 검색어가 없을 때만 판정 칸을 믿는다. ('도로 단위'는 도로 이름 규칙도 맞아야 인정)
        flag_status = None
        for flag, st in (("no_location", "위치 없음"), ("outside_seongnam", "성남 밖"),
                         ("segment", "구간"), ("road_only", "도로 단위")):
            if ai.get(flag):
                flag_status = st
                break
        if flag_status == "도로 단위" and not any(rules.ROAD_RE.match(rules.core_name(q)) for q in ai["queries"] or [r["query"]]):
            flag_status = None
        if not ai["queries"] and flag_status:
            row.update(단계="AI", 상태=flag_status)
            return row
        for q in ai["queries"]:
            row["검색어"] = q
            hit = _try_internal(rules.core_name(q), gu)
            if hit:
                return _fill(hit, "AI+내부대조")
            if USE_VWORLD:
                hit, last = _try_vworld(q, "장소", gu)
                if hit:
                    return _fill(hit, "AI+브이월드")

    if ai and flag_status:
        row.update(단계="AI", 상태=flag_status)
        return row
    row.update(단계="끝", 상태=last if last not in ("통과",) else "못 찾음")
    return row


# ======================================================================
# 단속장소·민원용: '동 + 도로 + 랜드마크' 쪼개기 → 랜드마크 검색 → 도로·동 단서로 검증
# ======================================================================
def _try_vworld_hint(query: str, kind: str, gu: str | None, hint: dict, strict: bool = False):
    from . import vworld
    if kind == "지번주소":
        g = vworld.geocode(f"경기도 성남시 {gu or ''} {query}".replace("  ", " "), "PARCEL")
        if not g:
            return None, "못 찾음", None
        st, info = validate.check(g, query, gu, need_name=False)
        return ({**g, **info}, "통과", None) if st == "통과" else (None, st, None)
    last = "못 찾음"
    for c in vworld.search_place(query):
        st, info = validate.check(c, query, gu, need_name=True)
        if st != "통과":
            last = st
            continue
        if validate.dong_conflict(c, hint):
            last = "단서 불일치"          # 원문 동과 결과 동이 다름 (금곡동 → 이매동)
            continue
        h = validate.hint_ok(c, hint)
        d = validate.road_near_m(hint.get("road"), c["lat"], c["lon"])
        if h is not True and d is not None and d <= validate.ROAD_NEAR_M:
            h = True                      # 모퉁이 건물: 주소는 옆 도로지만 원문 도로가 300m 안을 지남
        if h is not True and d is not None and d > 600:
            last = "단서 불일치"          # 원문 도로에서 600m 넘게 떨어짐
            continue
        ns = validate.name_score(query, c.get("title", ""))
        if hint.get("필수") and not h:
            last = "단서 불일치"          # 흔한 이름인데 원문의 도로·동과 안 맞음
            continue
        if h is False and (ns != "강함" or strict):
            last = "단서 불일치"          # 도로가 다른데 이름이 확실하지 않거나, 줄인 이름·AI 검색어로 찾음
            continue
        if strict and ns == "약함":
            last = "이름 불일치"          # 짧게 줄인 이름·AI 검색어로 찾은 결과는 더 엄격히
            continue
        if h is None and hint.get("road"):
            h = False                     # 원문 도로가 있는데 결과 주소·근접 어느 쪽으로도 확인 안 됨 → 신뢰도 '낮음'(보류)
        return {**c, **info}, "통과", h
    return None, last, None


def process_place(raw: str, gu: str | None, context: str) -> dict:
    if isinstance(gu, float):              # pandas 빈칸(NaN) → None
        gu = None
    strict_all = gu is None                # 구를 모르면 구 검증이 없으니 이름을 더 엄격하게 본다
    row = {"원문": raw, "구_기대": gu, "단계": None, "상태": None, "검색어": None,
           "장소_종류": None, "단서_동": None, "단서_도로": None, "결과_이름": None, "결과_주소": None,
           "사용_API": None, "위도": None, "경도": None, "gid": None, "AI_설명": None,
           "이름점수": None, "단서일치": None, "신뢰도": None}
    r = rules.classify_place(raw)
    hint = r.get("hint", {})
    row.update(검색어=r["query"], 장소_종류=r["kind"], 단서_동=hint.get("dong"), 단서_도로=hint.get("road"))
    if r["status"] in ("위치 없음", "구간", "도로 단위", "성남 밖"):
        row.update(단계="규칙", 상태=r["status"])
        return row

    def _fill(hit, stage, h):
        api = hit.get("api") or ""
        row.update(단계=stage, 상태="성공", 위도=round(hit["lat"], 6), 경도=round(hit["lon"], 6),
                   gid=hit["gid"], 결과_이름=hit.get("title"), 결과_주소=hit.get("address"), 사용_API=api)
        g_stage = stage + ("·주소" if api.startswith("주소") else "")
        g = validate.grade(g_stage, row["검색어"], hit.get("title"), hit["lat"], hit["lon"], "일반", hint=h)
        row.update(이름점수=g["이름점수"], 단서일치=g["단서일치"], 신뢰도=g["신뢰도"])
        return row

    ambiguous = r["status"] == "이름 모호"
    need_hint = bool(hint.get("필수"))
    # 1) 내부 대조 — 주소가 없는 자료라 단서 검증을 못 하므로, 흔한 이름이면 건너뜀
    def _internal_checked(q):
        """내부 대조 + (브이월드 사용 시) 좌표→주소로 원문 도로·동 단서 확인."""
        hit = _try_internal(q, gu)
        if not hit:
            return None, None
        h = None
        if USE_VWORLD and (hint.get("road") or hint.get("dong")):
            from . import vworld
            rev = {"address": vworld.reverse(hit["lat"], hit["lon"])}
            if validate.dong_conflict(rev, hint):
                return None, False
            h = validate.hint_ok(rev, hint)
            d = validate.road_near_m(hint.get("road"), hit["lat"], hit["lon"])
            if h is not True and d is not None and d <= validate.ROAD_NEAR_M:
                h = True
            if h is False:
                return None, False          # 같은 이름의 다른 지점
        return hit, h

    if not ambiguous and not need_hint and r["kind"] == "장소":
        hit, h = _internal_checked(r["query"])
        if hit:
            return _fill(hit, "규칙+내부대조", h)
    # 2) 브이월드 (규칙 검색어 = AI 없는 기준선)
    last = "이름 모호" if ambiguous else "못 찾음"
    if USE_VWORLD and not ambiguous:
        hit, last, h = _try_vworld_hint(r["query"], r["kind"], gu, hint, strict=strict_all)
        if hit:
            return _fill(hit, "규칙+브이월드", h)
        for alt in rules.synonyms(r["query"] or "") + rules.variants(r["query"] or ""):
            hit, _, h = _try_vworld_hint(alt, "장소", gu, hint, strict=True)
            if hit:
                row["검색어"] = alt
                return _fill(hit, "규칙+브이월드", h)
    if r["kind"] == "지번주소":
        row.update(단계="끝", 상태=last)
        return row
    # 3) AI 다듬기
    ai = llm.refine(raw, gu, context)
    if ai:
        row["AI_설명"] = ai.get("reason")
        qs = [rules.sanitize_query(q, raw) for q in ai["queries"]]
        stem, road_c = rules.road_stem(hint.get("road")), rules.compact(hint.get("road") or "")
        qs = [q for i, q in enumerate(qs) if q and q not in qs[:i] and q != r["query"]
              and not (road_c and (q == road_c or road_c.startswith(q) or q == stem))]   # 판교역로 → '판교역' 금지
        for q in qs:
            row["검색어"] = q
            q_generic = q in rules.GENERIC
            if not q_generic and not need_hint:
                hit, h = _internal_checked(q)
                if hit:
                    return _fill(hit, "AI+내부대조", h)
            if USE_VWORLD:
                h_req = {**hint, "필수": need_hint or q_generic}
                hit, last, h = _try_vworld_hint(q, "장소", gu, h_req, strict=True)
                if hit:
                    return _fill(hit, "AI+브이월드", h)
        if not qs and ai.get("road_only") and hint.get("road"):
            row.update(단계="AI", 상태="도로 단위")
            return row
    row.update(단계="끝", 상태=last if last != "통과" else "못 찾음")
    return row



# ======================================================================
# 설치주소처럼 주소 글자가 있을 때: 주소 정리 → 주소 검색 (규칙, AI 없음)
# ======================================================================
def by_address(addr: str, gu: str | None, profile: str = "교차로") -> dict | None:
    if not USE_VWORLD:
        return None
    from . import vworld
    for q, kind in rules.clean_address(addr, gu):
        g = vworld.geocode(q, kind)
        if not g:
            continue
        st, info = validate.check(g, q, gu, need_name=False)
        if st == "통과":
            row = {"원문": addr, "구_기대": gu, "단계": "규칙+주소검색", "상태": "성공", "검색어": q,
                   "결과_이름": g["title"], "결과_주소": g["address"], "사용_API": g["api"],
                   "위도": round(g["lat"], 6), "경도": round(g["lon"], 6), "gid": info["gid"]}
            row.update(validate.grade("규칙+주소검색·주소", q, g["title"], g["lat"], g["lon"], profile))
            return row
    return None
