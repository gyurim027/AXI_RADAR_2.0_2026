"""2단계: API 없이 통합본 내부 자료(신호기 교차로명·바닥신호등·버스정류장명)와 이름 대조.

같은 이름이 여러 곳이면 서로 300m 안에 모일 때만 평균 좌표를 쓰고, 흩어져 있으면 쓰지 않는다.
"""
import re
import pandas as pd
from .config import DATA
from .rules import core_name, GENERIC
from .grid import haversine_m

_ref = pd.read_csv(DATA / "ref_places.csv")
_ref["core"] = _ref["이름"].astype(str).map(core_name)
_ref = _ref[_ref["core"].str.len() >= 3]


def match(core: str, gu: str | None):
    if not core or len(core) < 3 or core in GENERIC:
        return None
    r = _ref
    if gu:
        r = r[r["구"] == gu]
    hit = r[r["core"] == core]
    if hit.empty:  # 앞부분 일치 (예: 하원초등학교 ↔ 하원초등학교후문)
        # 기준 자료 이름이 검색어로 시작할 때만. 단, '판교테크노1' ↔ '판교테크노14'처럼 숫자가 이어지면 다른 곳
        pat = "^" + re.escape(core) + (r"(?!\d)" if core[-1:].isdigit() else "")
        hit = r[r["core"].str.contains(pat, regex=True)]
    if hit.empty:
        return None
    lat, lon = hit["위도"].mean(), hit["경도"].mean()
    spread = max(haversine_m(lat, lon, a, b) for a, b in zip(hit["위도"], hit["경도"]))
    if spread > 300:
        return {"ambiguous": True, "n": len(hit)}
    return {
        "ambiguous": False,
        "lat": lat, "lon": lon,
        "matched": "; ".join(hit["이름"].astype(str).unique()[:3]),
        "source": "; ".join(hit["출처"].unique()),
        "n": len(hit),
    }
