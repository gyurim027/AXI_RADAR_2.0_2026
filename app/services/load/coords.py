"""7장 좌표 → 격자(gid). 본문 위치값만 쓴다 (브이월드 주소 변환은 이번 범위 밖).

EPSG:4326 → EPSG:5179(Korea 2000 Unified CS, 횡메르카토르) 변환은 수식으로 직접 계산한다 (pyproj 불필요).
격자: (x // 250, y // 250) 를 grid_cell 칸 중심점을 같은 방식으로 바꾼 값 round((c - 125) / 250) 과 맞춘다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

# GRS80, EPSG:5179: lat0=38, lon0=127.5, k0=0.9996, FE=1,000,000, FN=2,000,000
_A = 6378137.0
_F = 1 / 298.257222101
_K0, _LAT0, _LON0, _FE, _FN = 0.9996, math.radians(38.0), math.radians(127.5), 1_000_000.0, 2_000_000.0

_n = _F / (2 - _F)
_AA = _A / (1 + _n) * (1 + _n**2 / 4 + _n**4 / 64 + _n**6 / 256)
_ALPHA = (
    _n / 2 - 2 * _n**2 / 3 + 5 * _n**3 / 16 + 41 * _n**4 / 180,
    13 * _n**2 / 48 - 3 * _n**3 / 5 + 557 * _n**4 / 1440,
    61 * _n**3 / 240 - 103 * _n**4 / 140,
    49561 * _n**4 / 161280,
)
_E = math.sqrt(_F * (2 - _F))


def _meridian(phi: float) -> float:
    t = math.sinh(math.atanh(math.sin(phi)) - _E * math.atanh(_E * math.sin(phi)))
    xi = math.atan(t)
    s = xi + sum(a * math.sin(2 * (j + 1) * xi) for j, a in enumerate(_ALPHA))
    return s


def to_5179(lat: float, lon: float) -> tuple[float, float]:
    phi, lam = math.radians(lat), math.radians(lon) - _LON0
    t = math.sinh(math.atanh(math.sin(phi)) - _E * math.atanh(_E * math.sin(phi)))
    # Krüger 급수
    chi = math.atan(t)                                  # 등각위도
    xi_p = math.atan2(math.tan(chi), math.cos(lam))
    eta_p = math.atanh(math.sin(lam) * math.cos(chi))
    xi = xi_p + sum(a * math.sin(2 * (j + 1) * xi_p) * math.cosh(2 * (j + 1) * eta_p) for j, a in enumerate(_ALPHA))
    eta = eta_p + sum(a * math.cos(2 * (j + 1) * xi_p) * math.sinh(2 * (j + 1) * eta_p) for j, a in enumerate(_ALPHA))
    x = _FE + _K0 * _AA * eta
    y = _FN + _K0 * _AA * (xi - _meridian(_LAT0))
    return x, y


def cell_key(lat: float, lon: float) -> tuple[int, int]:
    x, y = to_5179(lat, lon)
    return int(x // 250), int(y // 250)


@dataclass(frozen=True)
class Cell:
    gid: str
    gu: str | None
    dong: str | None


class Grid:
    """grid_cell 칸 목록. rows: (gid, center_lat, center_lon, gu_center, admin_dong_center)."""

    def __init__(self, rows: Iterable[tuple]):
        self._by_key: dict[tuple[int, int], Cell] = {}
        for gid, clat, clon, gu, dong in rows:
            cx, cy = to_5179(clat, clon)
            self._by_key[(round((cx - 125) / 250), round((cy - 125) / 250))] = Cell(gid, gu, dong)

    def __len__(self) -> int:
        return len(self._by_key)

    def find(self, lat: float, lon: float) -> Cell | None:
        return self._by_key.get(cell_key(lat, lon))


POS_RE = re.compile(r"위도\s*:\s*(-?\d+\.\d+)\s*경도\s*:\s*(-?\d+\.\d+)")


def body_position(body: str) -> tuple[float, float] | None:
    m = POS_RE.search(body or "")
    if not m:
        return None
    lat, lon = float(m[1]), float(m[2])
    return (lat, lon) if 30 < lat < 45 and 120 < lon < 135 else None


def locate(body: str, grid: Grid) -> dict:
    """lat · lon · gid · coord_method · coord_accuracy · (격자 구·동)."""
    out = dict(lat=None, lon=None, gid=None, coord_method=None, coord_accuracy=None, grid_gu=None, grid_dong=None)
    pos = body_position(body)
    if pos is None:
        return out
    lat, lon = pos
    out.update(lat=lat, lon=lon)
    cell = grid.find(lat, lon)
    if cell is None:
        out["coord_method"] = "원본 좌표(성남 격자 밖)"
        return out
    out.update(gid=cell.gid, coord_method="원본 좌표(본문 위치값)", coord_accuracy="원본 좌표",
               grid_gu=cell.gu, grid_dong=cell.dong)
    return out
