"""3단계: 브이월드 좌표 찾기. 해외 IP는 막히니 국내 PC에서 실행.

- 주소 검색(지오코더 2.0): /req/address  request=getcoord, type=ROAD|PARCEL
- 장소 검색(검색 API 2.0): /req/search   request=search,  type=PLACE, bbox로 성남 범위 제한
응답은 캐시(out/ai03/vworld_cache.json)에 남겨 같은 검색어를 다시 부르지 않는다.
"""
import json
import time
import requests
from .config import VWORLD_KEY, SEONGNAM_BBOX, VWORLD_SLEEP, OUT

BASE = "https://api.vworld.kr/req"


class VWorldError(RuntimeError):
    """한도 초과·키 오류 등. 캐시에 저장하지 않고 실행을 멈춘다 (다음 날 이어서 돌리기 위해)."""
_cache_path = OUT / "vworld_cache.json"
_cache = json.loads(_cache_path.read_text(encoding="utf-8")) if _cache_path.exists() else {}
calls = 0


def _get(url, params):
    global calls
    key = url + "|" + json.dumps(params, ensure_ascii=False, sort_keys=True)
    if key in _cache:
        return _cache[key]
    if not VWORLD_KEY:
        raise RuntimeError("VWORLD_KEY 환경변수가 없습니다.")
    for attempt in range(3):                    # 응답 지연 대비 3번까지 재시도
        try:
            r = requests.get(url, params={**params, "key": VWORLD_KEY}, timeout=20)
            r.raise_for_status()
            try:
                data = r.json()
            except ValueError:            # 응답 안에 제어 문자가 섞인 경우 (금곡공원 검색 등)
                data = json.loads(r.text, strict=False)
            res = data.get("response", {})
            if res.get("status") == "ERROR":        # NOT_FOUND(결과 없음)와 다름: 한도 초과·키 오류 등
                err = res.get("error", {})
                raise VWorldError(f"{err.get('code', 'ERROR')}: {err.get('text', '')}")
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    calls += 1
    _cache[key] = data
    time.sleep(VWORLD_SLEEP)
    return data


def save_cache():
    _cache_path.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")


def geocode(address: str, kind: str = "ROAD"):
    """주소 → {lat, lon, title, address, api}. 못 찾으면 None."""
    data = _get(f"{BASE}/address", {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "refine": "true", "simple": "false",
        "format": "json", "type": kind, "address": address,
    })
    res = data.get("response", {})
    if res.get("status") != "OK":
        return None
    p = res["result"]["point"]
    refined = res.get("refined", {}).get("text", address)
    return {"lat": float(p["y"]), "lon": float(p["x"]), "title": refined,
            "address": refined, "api": f"주소 검색({'도로명' if kind == 'ROAD' else '지번'})"}


def search_place(query: str, size: int = 5):
    """장소 이름 → 후보 목록 [{lat, lon, title, address, category, api}]."""
    data = _get(f"{BASE}/search", {
        "service": "search", "request": "search", "version": "2.0",
        "crs": "EPSG:4326", "bbox": ",".join(map(str, SEONGNAM_BBOX)),
        "size": size, "page": 1, "query": query, "type": "place",
        "format": "json", "errorformat": "json",
    })
    res = data.get("response", {})
    if res.get("status") != "OK":
        return []
    out = []
    for it in res.get("result", {}).get("items", []):
        addr = it.get("address", {}) or {}
        out.append({
            "lat": float(it["point"]["y"]), "lon": float(it["point"]["x"]),
            "title": it.get("title", ""),
            "address": " ".join(x for x in (addr.get("road"), addr.get("parcel")) if x),
            "category": it.get("category", ""), "api": "장소 검색",
        })
    return out


def reverse(lat: float, lon: float) -> str:
    """좌표 → 주소 글자(도로명+지번). 내부 대조로 찾은 좌표가 원문의 도로·동과 맞는지 볼 때 쓴다."""
    data = _get(f"{BASE}/address", {
        "service": "address", "request": "getAddress", "version": "2.0",
        "crs": "epsg:4326", "point": f"{lon:.6f},{lat:.6f}", "type": "both",
        "format": "json", "simple": "false",
    })
    res = data.get("response", {})
    if res.get("status") != "OK":
        return ""
    return " ".join(r.get("text", "") for r in res.get("result", []))
