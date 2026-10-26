"""원천·결과 표 읽기 — 공용 DB(app/core/db.py)에서 읽고, --csv(또는 RADAR_V2_CSV_DIR)면 v2 CSV 폴더에서 읽는다.

    from app.services.grid import source as S
    S.use_csv(path)                      # 선택: CSV 폴더로 바꾸기
    d = S.read("src_complaint", usecols=["complaint_id", "gid"])
    S.columns("src_crosswalk") · S.tables()
CSV 모드에서는 install_db_shim()으로 app.core.db.read_only를 CSV(메모리 SQLite)로 바꿔
DB를 읽는 코드(은경 ext_columns.py)도 같은 자료로 돌릴 수 있다 (DB가 열리기 전·미리 보기용).
"""
from __future__ import annotations

import re
import sqlite3
import sys
import types
from pathlib import Path

import pandas as pd

from . import config as C

_csv: Path | None = C.V2_CSV_DIR


def use_csv(path: str | Path | None) -> None:
    global _csv
    _csv = Path(path) if path else None


def using_csv() -> bool:
    return _csv is not None


def _csv_root() -> Path:
    """CSV가 바로 안에 없으면 한두 겹 아래에서 찾는다 (압축을 풀면 같은 이름 폴더가 한 겹 더 생기는 경우)."""
    if any(_csv.glob("[0-9][0-9]_*.csv")):
        return _csv
    for p in sorted(_csv.glob("*/")) + sorted(_csv.glob("*/*/")):
        if any(p.glob("[0-9][0-9]_*.csv")):
            return p
    raise FileNotFoundError(f"{_csv} 안에 v2 CSV(01_grid_cell.csv 등)가 없습니다 — .env의 RADAR_V2_CSV_DIR를 확인하세요")


def _csv_path(name: str) -> Path:
    hit = sorted(_csv_root().glob(f"[0-9][0-9]_{name}.csv"))
    if not hit:
        raise FileNotFoundError(f"{_csv_root()}에 {name} 표가 없습니다")
    return hit[0]


def tables() -> list[str]:
    if _csv:
        return [re.sub(r"^\d\d_", "", p.stem) for p in sorted(_csv_root().glob("[0-9][0-9]_*.csv"))]
    from app.core import db
    return [list(r.values())[0] for r in db.read_only("SHOW TABLES")]


def columns(name: str) -> list[str]:
    if _csv:
        return list(pd.read_csv(_csv_path(name), nrows=0).columns)
    from app.core import db
    return [r["Field"] for r in db.read_only(f"SHOW COLUMNS FROM `{name}`")]


def read(name: str, usecols: list[str] | None = None, **kw) -> pd.DataFrame:
    """표 하나를 DataFrame으로. kw는 CSV일 때 read_csv에 넘긴다 (dtype·keep_default_na 등)."""
    if _csv:
        return pd.read_csv(_csv_path(name), usecols=usecols, low_memory=False, **kw)
    from app.core import db
    cols = ", ".join(f"`{c}`" for c in usecols) if usecols else "*"
    d = pd.DataFrame(db.read_only(f"SELECT {cols} FROM `{name}`"))
    if d.empty:
        d = pd.DataFrame(columns=usecols or columns(name))
    if kw.get("dtype") is str:
        d = d.astype(object).where(d.notna(), None).astype("string").astype(object)
    return d


# ── CSV 모드에서 app.core.db.read_only를 CSV로 바꾸기 (ext_columns용) ─────────────
_NEED = {"grid_cell", "grid_feature", "grid_feature_ng", "src_ped_hotspot_5y", "src_signal_controller", "src_hump_crosswalk",
         "src_ped_priority_candidate", "src_floor_signal", "src_bike_road", "src_parking_enforce_place", "assess_crosswalk",
         "assess_sidewalk", "assess_intersection", "assess_zone", "src_enforce_camera_all", "src_red_surface", "src_zone_sign"}


def _typed(d: pd.DataFrame) -> pd.DataFrame:
    for c in d.columns:
        n = pd.to_numeric(d[c], errors="coerce")
        if d[c].notna().sum() and n.notna().sum() == d[c].notna().sum() and n.abs().max() < 2**62:
            d[c] = n
    return d


def install_db_shim(overrides: dict | None = None):
    """CSV 모드 전용. overrides: {표 이름: DataFrame} — AI-03 결과를 넣은 원천 표로 셀 때."""
    if not _csv:
        return None
    con = sqlite3.connect(":memory:")
    for name in _NEED:
        try:
            d = overrides[name].copy() if overrides and name in overrides else \
                pd.read_csv(_csv_path(name), dtype=str, keep_default_na=False, na_values=[""])
        except FileNotFoundError:
            continue
        _typed(d.astype(object).where(d.notna(), None)).to_sql(name, con, index=False)
    con.row_factory = sqlite3.Row
    import app.core.db as real
    real.read_only = lambda sql, args=(): [dict(r) for r in con.execute(sql.replace("%%", "%"), args or ()).fetchall()]
    for m in [k for k in sys.modules if k.startswith("app.services.grid.ext_columns")]:
        del sys.modules[m]
    return real
