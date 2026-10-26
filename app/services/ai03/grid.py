"""좌표 → gid. 적재 규칙 명세서 7장 방식: EPSG:5179로 바꾼 뒤 250m로 나눠 칸을 찾는다.

grid_cell(2,406칸)의 중심좌표를 EPSG:5179로 바꾸면 모두 250m 격자의 중심(나머지 125m)에 놓인다.
그래서 (x // 250, y // 250) 칸 번호 → gid 표를 만들고, 점이 들어간 칸이 grid_cell에 없으면 '격자 밖'.
"""
import math
import pandas as pd
from pyproj import Transformer
from .config import DATA

CELL = 250.0
_to5179 = Transformer.from_crs(4326, 5179, always_xy=True)

_g = pd.read_csv(DATA / "grid_cell.csv")
_gx, _gy = _to5179.transform(_g["center_lon"].to_numpy(), _g["center_lat"].to_numpy())
_index = {(int(x // CELL), int(y // CELL)): gid for x, y, gid in zip(_gx, _gy, _g["gid"])}
_center = {gid: (x, y) for x, y, gid in zip(_gx, _gy, _g["gid"])}
assert len(_index) == len(_g), "grid_cell 중심이 250m 격자에 맞지 않습니다"


def to_gid(lat: float, lon: float):
    """(gid, 칸 중심까지 거리m) — 성남 격자 밖이면 (None, None)."""
    x, y = _to5179.transform(lon, lat)
    gid = _index.get((int(x // CELL), int(y // CELL)))
    if gid is None:
        return None, None
    cx, cy = _center[gid]
    return gid, round(math.hypot(x - cx, y - cy), 1)


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))
