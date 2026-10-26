"""5단계: 검증. 하나라도 통과 못 하면 쓰지 않는다 (NULL 유지)."""
import re
import numpy as np
import pandas as pd
from .config import DATA
from .grid import to_gid
from .rules import compact, core_name, VOLATILE_RE

# 신호등·횡단보도·바닥신호등·신호기 좌표 2,503곳 (통합본 35·18·50·41)
_sp = pd.read_csv(DATA / "ref_signal_points.csv")
_sla, _slo = np.radians(_sp["위도"].to_numpy()), np.radians(_sp["경도"].to_numpy())
SIGNAL_NEAR_M = 150

LEGAL_RE = re.compile(r"\((주|유|사|재)\)|주식회사|유한회사")
TAIL_RE = re.compile(r"(\(버스정류장\)|\(마을\)|버스정류장|정류장|/\d+동|\d+동앞?|입구|출구|정문|후문|앞|옆|건너|사거리|삼거리|오거리|단일로|교차로)$")

GU_RE = re.compile(r"(수정구|중원구|분당구)")


def _bigrams(s):
    s = compact(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


CATEGORY_RE = re.compile(r"(초등학교|중학교|고등학교|여자중학교|여자고등학교|대학교|학교|아파트|빌라|교회|성당|병원|의원|공원|"
                         r"행정복지센터|센터|주차장|공영주차장|시장|마트|은행|지구대|파출소|우체국|오피스텔|빌딩|단지)$")


def name_ok(query: str, title: str) -> bool:
    """검색어 핵심 이름과 결과 이름이 겹치는지. '금곡초등학교'와 '청솔초등학교'처럼
    분류어(초등학교 등)만 겹치는 경우는 불일치로 본다."""
    q, t = core_name(query), compact(title)
    if not q or not t:
        return False
    if q in t or core_name(t) in q:
        return True
    qh = CATEGORY_RE.sub("", q)
    if qh != q:                                    # 분류어를 빼고 앞부분(고유 이름)끼리 비교
        if len(qh) < 2:
            return False
        a, b = _bigrams(qh), _bigrams(t)
        return bool(a) and len(a & b) / len(a) >= 0.6 if len(qh) > 2 else qh in t
    a, b = _bigrams(q), _bigrams(t)
    return bool(a) and len(a & b) / len(a) >= 0.6


def check(cand: dict, query: str, expect_gu: str | None, need_name=True) -> tuple[str, dict]:
    gid, dist = to_gid(cand["lat"], cand["lon"])
    info = {"gid": gid, "격자거리m": dist}
    if gid is None:
        return "격자 밖", info
    addr = (cand.get("address", "") or "") + " " + (cand.get("title", "") or "")
    if addr.strip() and not re.search(r"성남", addr) and re.search(r"(서울|용인|광주시|하남|과천|의왕|수원)", addr):
        return "성남 밖", info
    m = GU_RE.search(addr)
    got_gu = m.group(1) if m else cand.get("gu")
    info["결과_구"] = got_gu
    if expect_gu and not got_gu:
        return "구 확인 불가", info       # 주소가 없으면 통과시키지 않는다
    if expect_gu and got_gu != expect_gu:
        return "구 불일치", info
    if need_name and not name_ok(query, cand.get("title", "")):
        return "이름 불일치", info
    return "통과", info



def nearest_signal_m(lat, lon) -> float:
    la, lo = np.radians(lat), np.radians(lon)
    d = np.sqrt((_sla - la) ** 2 + ((_slo - lo) * np.cos(la)) ** 2) * 6371000
    return round(float(d.min()), 1)


def _norm_center(n):
    return re.sub(r"(\d?)동(행정복지센터|주민센터)", r"\1\2", n)   # 판교동행정복지센터 ≈ 판교행정복지센터


def _strip(n):
    n = compact(LEGAL_RE.sub("", str(n)))
    for _ in range(3):
        n = TAIL_RE.sub("", n)
    return core_name(n)


def name_score(query: str, title: str) -> str:
    """강함: 핵심 이름이 같음 / 보통: 앞뒤 2글자 이내 차이 / 약함: 그 외 (다른 업종 말이 붙음 등)."""
    q = _norm_center(core_name(compact(query)))
    best = "약함"
    for t in re.split(r"[;.,·()]", str(title or "")):
        t = _norm_center(_strip(t))
        if not t:
            continue
        if t == q or core_name(t) == q:
            return "강함"
        if q.endswith("교") and re.search(re.escape(q) + r"회", t):
            continue                   # 다리(○○교)와 교회(○○교회)는 다른 곳 (둔전교 → 둔전교회, 평가 오연결 2건)
        if q in t or t in q:
            extra = len(t.replace(q, "")) if q in t else len(q.replace(t, ""))
            if extra <= 2:
                best = "보통"
    return best


def grade(stage: str, query: str, title: str, lat: float, lon: float, profile: str, hint=None) -> dict:
    """신뢰도 높음/보통/낮음. 보통·낮음만 사람이 검수한다.
    profile='교차로': 이름 + 신호 지점 거리 / profile='일반': 이름만 (민원 등 교차로가 아닌 곳)"""
    ns = "강함" if stage.endswith("주소") else name_score(query, title)
    dist = nearest_signal_m(lat, lon)
    score = (ns == "강함") * 1
    if profile == "교차로":
        score += dist <= SIGNAL_NEAR_M
    elif hint is not None:
        score += bool(hint)            # 원문의 도로·동이 결과 주소와 맞음
    else:
        score += ns == "강함"          # 단서가 없으면 이름만으로 판단
    if stage.startswith("AI"):
        score -= 1                     # AI가 바꾼 검색어는 한 단계 낮게
    if VOLATILE_RE.search(query or "") and not stage.endswith("주소"):
        score = min(score, 0)          # 지구대·파출소 등은 옮기거나 이름이 바뀌어 옛 위치가 남음 → 사람 확인 전엔 보류
                                       # (성호지구대·성호파출소: 경찰 신호·신호기 검수 틀림, 평가 오연결 2건)
    g = "높음" if score >= 2 else ("보통" if score == 1 else "낮음")
    if ns == "약함" and "브이월드" in stage and hint is not True:
        g = "낮음"                     # 이름이 일부만 겹치고 도로·동 단서도 없음 (동안 → 미금동안마녀의원) → 보류
    if ns == "약함" and hint is True and g == "낮음":
        g = "보통"                     # 도로·동이 맞으면 이름에 말이 더 붙어도 인정 (표본 20곳 중 틀림 0)
    if hint is False:
        g = "낮음"                     # 원문 도로·동과 결과 주소가 다름 → 사람 확인 전엔 반영 보류
    return {"이름점수": ns, "신호거리m": dist, "단서일치": hint, "신뢰도": g}



_ROAD_IN_ADDR = re.compile(r"([가-힣0-9]+?(?:대로|로|길)(?:\d+번?길)?)(?=\s?\d|\s|$)")


def _addr_roads(addr: str) -> set:
    return {compact(t) for t in _ROAD_IN_ADDR.findall(addr or "")}


_ROAD_NUM = re.compile(r"([가-힣0-9]+?(?:대로|로|길))(?:(\d+)번?길)?\s?(\d+)?(?=-|\s|$|[가-힣])")
ADDR_NUM_GAP = 30          # 건물번호 1 ≈ 10m → 30 ≈ 300m


def _split_road(r: str):
    """'산성대로97번길' → ('산성대로', 97), '서판교로44길' → ('서판교로', 44), '황새울로' → ('황새울로', None)"""
    m = re.fullmatch(r"([가-힣0-9]+?(?:대로|로|길))(\d+)번?길", compact(r))
    return (m.group(1), int(m.group(2))) if m else (compact(r), None)


def road_number_near(hint_road: str, addr: str) -> bool:
    """도로명주소 번호로 가까움 판단.
    '산성대로97번길' ↔ 주소 '산성대로 97'(갈라지는 자리) / '산성대로429번길' ↔ '산성대로437번길'(옆 골목)."""
    main, n = _split_road(hint_road)
    for road, side, bno in _ROAD_NUM.findall(addr or ""):
        if compact(road) != main:
            continue
        if n is None:
            return True                                   # 원문이 큰길이고 같은 큰길(의 번길)에 있음
        if side and abs(int(side) - n) <= ADDR_NUM_GAP:
            return True                                   # 옆 골목
        if not side and bno and abs(int(bno) - n) <= ADDR_NUM_GAP:
            return True                                   # 큰길의 갈라지는 자리 근처 건물
    return False


def hint_ok(cand: dict, hint: dict | None) -> bool | None:
    """찾은 곳 주소에 원문의 도로·동이 있는가. 단서가 없으면 None.
    도로는 글자 일부가 아니라 '도로 이름 통째로' 비교한다 ('대장로' ≠ '판교대장로').
    원문이 '○○번길'이면 번길까지 같아야 한다 ('성남대로926번길' ≠ '성남대로')."""
    if not hint or not (hint.get("road") or hint.get("dong")):
        return None
    addr_raw = cand.get("address", "") or ""
    roads = _addr_roads(addr_raw)
    road = compact(hint.get("road") or "")
    if road:
        if road in roads or road_number_near(road, addr_raw):
            return True
        if not re.search(r"\d+번?길$", road):          # 원문이 큰길이면 그 큰길의 번길도 인정 (성남대로 ↔ 성남대로144번길)
            if any(re.fullmatch(re.escape(road) + r"\d+번?길", t) for t in roads):
                return True
    dong = hint.get("dong")
    if dong:
        d = re.sub(r"\d동$", "동", dong)
        if re.search(r"(^|\s)" + re.escape(d) + r"(\s|$)", addr_raw) or re.search(r"(^|\s)" + re.escape(dong) + r"(\s|$)", addr_raw):
            return True
    if road and not roads and not dong:
        return None                      # 결과에 도로명 주소가 없으면 판단 불가
    return False


# ---- 원문 도로가 실제로 결과 근처를 지나는지 (모퉁이 건물은 옆 도로 주소를 쓰는 경우가 많음) ----
_rp_path = DATA / "ref_road_points.csv"
_rp = pd.read_csv(_rp_path) if _rp_path.exists() else pd.DataFrame(columns=["road", "위도", "경도"])
_rp_group = {k: (np.radians(v["위도"].to_numpy()), np.radians(v["경도"].to_numpy())) for k, v in _rp.groupby("road")}
ROAD_NEAR_M = 300


def road_near_m(road: str | None, lat: float, lon: float) -> float | None:
    """같은 이름(번길까지)의 도로 위 기준점 중 가장 가까운 거리. 기준점이 없으면 None."""
    if not road:
        return None
    g = _rp_group.get(compact(road))
    if g is None:
        return None
    la, lo = np.radians(lat), np.radians(lon)
    d = np.sqrt((g[0] - la) ** 2 + ((g[1] - lo) * np.cos(la)) ** 2) * 6371000
    return round(float(d.min()), 1)


def dong_conflict(cand: dict, hint: dict | None) -> bool:
    """원문의 동과 결과 주소의 (법정)동이 다르면 True. 금곡동 → 이매동 같은 경우."""
    if not hint or not hint.get("dong"):
        return False
    dong = re.sub(r"\d동$", "동", hint["dong"])          # 구미1동 → 구미동
    found = re.findall(r"([가-힣]+동)\s?(?:산?\d)", cand.get("address", "") or "")
    found = [re.sub(r"\d동$", "동", f) for f in found]
    return bool(found) and dong not in found
