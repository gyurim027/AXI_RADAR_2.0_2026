"""AI-03 좌표 반영 — 배치가 만든 out/ai03/*_update.csv를 공용 DB의 좌표 칸에 쓴다 (A-07·C-06, 세은).

원칙 (공용 DB를 고치는 일이라 가장 조심한다)
- 미리 보기가 기본이다. --apply를 줘야만 쓴다. 미리 보기는 DB를 아무것도 바꾸지 않는다 (job_run 기록도 안 남김).
- **좌표가 빈 행에만** 쓴다: WHERE 키 = ? AND lat IS NULL AND lon IS NULL AND gid IS NULL. 이미 값이 있는 행은 건드리지 않는다.
- 반영 전에 그 행들의 현재 값을 백업 CSV로 저장한다. 되돌리기(--rollback)는 그 백업으로 한다.
- 표 하나를 한 거래로 쓴다. 한 행이라도 계획과 다르면(그새 다른 사람이 바꿨다 등) 그 표 전체를 되돌리고 멈춘다.
- 미리 보기에서 막는 것: DB에 없는 키 · 이미 좌표가 있는 행 · 격자(gid)가 grid_cell에 없음 · 칸 길이 초과 · 좌표와 gid가 안 맞음(pyproj가 있을 때) · 키 중복.
- 민원(79)의 구·행정동(gu·admin_dong_name)은 비어 있을 때만 채운다 (신고 원본의 구를 덮어쓰지 않는다).
  79의 db_last_updated_at(값을 바꾼 시각)은 DB가 자동으로 안 바꾸므로 반영한 행만 지금 시각으로 고친다 (백업에 옛 값을 두고 되돌릴 때 복원).
- 값은 항상 %s 자리표시자로 넘긴다. 표·칸 이름은 아래 TABLES에 적힌 것만 쓴다.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

TABLES: dict[str, dict] = {
    "parking":   {"table": "src_parking_enforce_place", "key": "row_id", "key_type": int,
                  "set": ["lat", "lon", "gid", "grid_no", "gu_by_coord", "admin_dong_by_coord", "coord_method", "coord_accuracy"],
                  "fill_if_blank": [], "touch": []},
    "signal":    {"table": "src_signal_controller", "key": "row_id", "key_type": int,
                  "set": ["lat", "lon", "gid", "grid_no", "gu_by_coord", "admin_dong_by_coord", "coord_method", "coord_accuracy"],
                  "fill_if_blank": [], "touch": []},
    "police":    {"table": "src_police_signal", "key": "src_id", "key_type": int,
                  "set": ["lat", "lon", "gid", "location_method"], "fill_if_blank": [], "touch": []},
    "complaint": {"table": "src_complaint", "key": "complaint_id", "key_type": str,
                  "set": ["lat", "lon", "gid", "coord_method", "coord_accuracy"],
                  "fill_if_blank": ["gu", "admin_dong_name"],
                  "touch": ["db_last_updated_at"]},          # 79: 값을 바꾼 시각 칸 (DB가 자동으로 안 바꿔서 직접 지금으로)
}
GUARD = "lat IS NULL AND lon IS NULL AND gid IS NULL"
CHUNK = 500

# 상태 (미리 보기 표에 그대로 나온다)
OK, MISSING, HAS_COORD, NO_GRID, TOO_LONG, GID_MISMATCH, BAD_VALUE, DUP_KEY = (
    "반영", "DB에 없음", "이미 좌표 있음", "격자 없음", "칸 길이 초과", "좌표·gid 불일치", "값 이상", "키 중복")


class Store(Protocol):
    """DB 접근을 한 곳에 모은다 (시험에서는 sqlite로 바꿔 끼운다)."""
    def fetch(self, sql: str, args: tuple = ()) -> list[dict]: ...
    def column_limits(self, table: str, cols: Iterable[str]) -> dict[str, int]: ...
    def begin(self) -> None: ...
    def execute(self, sql: str, args: tuple = ()) -> int: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class MySqlStore:
    """공용 DB (app.core.db). 읽기는 읽기 전용 거래, 쓰기는 연결 하나에 거래 하나."""

    def __init__(self):
        self._con = None
        self._cur = None

    def fetch(self, sql, args=()):
        from app.core import db
        return db.read_only(sql, args)

    def column_limits(self, table, cols):
        rows = self.fetch("SELECT column_name AS c, character_maximum_length AS n FROM information_schema.columns "
                          "WHERE table_schema = DATABASE() AND table_name = %s AND character_maximum_length IS NOT NULL",
                          (table,))
        want = set(cols)
        return {r["c"]: int(r["n"]) for r in rows if r["c"] in want and int(r["n"]) < 65535}

    def begin(self):
        from app.core import db
        self._con = db.raw_connection()
        self._cur = self._con.cursor()

    def execute(self, sql, args=()):
        self._cur.execute(sql, args)
        return self._cur.rowcount

    def commit(self):
        self._con.commit()

    def rollback(self):
        if self._con is not None:
            self._con.rollback()

    def close(self):
        if self._con is not None:
            self._con.close()
            self._con = self._cur = None


@dataclass
class Plan:
    name: str
    table: str
    key: str
    rows: list[dict] = field(default_factory=list)          # 파일의 행 + _status, _before(현재 DB 값)

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r["_status"] == status)

    def ok_rows(self) -> list[dict]:
        return [r for r in self.rows if r["_status"] == OK]

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r["_status"]] = out.get(r["_status"], 0) + 1
        return out


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == "")


def read_update_file(name: str, path: str | Path) -> list[dict]:
    """update.csv를 읽는다. 필요한 칸이 없으면 바로 멈춘다. review_result 같은 DB에 없는 칸은 버린다."""
    spec = TABLES[name]
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        head = reader.fieldnames or []
        need = [spec["key"], *spec["set"]]
        missing = [c for c in need if c not in head]
        if missing:
            raise ValueError(f"{Path(path).name}에 필요한 칸이 없습니다: {missing}")
        keep = [spec["key"], *spec["set"], *[c for c in spec["fill_if_blank"] if c in head]]
        return [{c: (None if _blank(r.get(c)) else r[c]) for c in keep} for r in reader]


OUTSIDE = "(성남 격자 밖)"


def _gid_from_coord(lat: float, lon: float) -> str | None:
    """좌표로 gid를 다시 계산한다. 격자 밖이면 OUTSIDE, pyproj가 없어 계산 못 하면 None(이 검사만 건너뜀)."""
    try:
        from app.services.ai03.grid import to_gid
    except Exception:
        return None
    try:
        g = to_gid(lat, lon)
        g = g[0] if isinstance(g, tuple) else g
        return g if g else OUTSIDE
    except Exception:
        return None


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def build_plan(name: str, path: str | Path, store: Store, check_gid: bool = True) -> Plan:
    spec = TABLES[name]
    table, key, kt = spec["table"], spec["key"], spec["key_type"]
    plan = Plan(name, table, key)
    raw = read_update_file(name, path)
    seen: set = set()
    for r in raw:
        r = dict(r)
        try:
            r[key] = kt(r[key])
            r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
            if not r.get("gid") or any(math.isnan(v) for v in (r["lat"], r["lon"])):
                raise ValueError
            r["_status"] = DUP_KEY if r[key] in seen else OK
            seen.add(r[key])
        except (TypeError, ValueError):
            r["_status"] = BAD_VALUE
        r["_before"] = None
        plan.rows.append(r)

    keys = [r[key] for r in plan.rows if r["_status"] == OK]
    cur: dict = {}
    cols = ", ".join(f"`{c}`" for c in [key, *spec["set"], *spec["fill_if_blank"], *spec["touch"]])
    for part in _chunks(keys, CHUNK):
        for d in store.fetch(f"SELECT {cols} FROM `{table}` WHERE `{key}` IN ({', '.join(['%s'] * len(part))})", tuple(part)):
            cur[d[key]] = d
    gids = sorted({r["gid"] for r in plan.rows if r["_status"] == OK})
    have: set = set()
    for part in _chunks(gids, CHUNK):
        have |= {d["gid"] for d in store.fetch(f"SELECT gid FROM grid_cell WHERE gid IN ({', '.join(['%s'] * len(part))})", tuple(part))}
    limits = store.column_limits(table, spec["set"] + spec["fill_if_blank"])
    for r in plan.rows:
        if r["_status"] != OK:
            continue
        d = cur.get(r[key])
        if d is None:
            r["_status"] = MISSING
            continue
        r["_before"] = d
        if not all(_blank(d.get(c)) for c in ("lat", "lon", "gid")):
            r["_status"] = HAS_COORD
        elif r["gid"] not in have:
            r["_status"] = NO_GRID
        elif any(c in limits and r.get(c) is not None and len(str(r[c])) > limits[c] for c in spec["set"] + spec["fill_if_blank"]):
            r["_status"] = TOO_LONG
        elif check_gid and (g := _gid_from_coord(r["lat"], r["lon"])) is not None and g != r["gid"]:
            r["_status"] = GID_MISMATCH
    return plan


def format_plan(plan: Plan, sample: int = 3) -> str:
    lines = [f"[{plan.name}] {plan.table}  파일 {len(plan.rows):,}행"]
    for st, n in sorted(plan.summary().items(), key=lambda x: (x[0] != OK, -x[1])):
        lines.append(f"  {st:<10} {n:>7,}")
    for r in plan.ok_rows()[:sample]:
        lines.append(f"  예) {plan.key}={r[plan.key]}  (지금 비어 있음) → lat={r['lat']:.6f} lon={r['lon']:.6f} gid={r['gid']}")
    return "\n".join(lines)


def write_plan_csv(plan: Plan, out_dir: Path, stamp: str) -> Path:
    p = out_dir / f"apply_plan_{plan.name}_{stamp}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([plan.key, "상태", "lat", "lon", "gid"])
        for r in plan.rows:
            w.writerow([r[plan.key], r["_status"], r.get("lat"), r.get("lon"), r.get("gid")])
    return p


def write_backup(plan: Plan, out_dir: Path, stamp: str) -> Path:
    """반영할 행의 지금 값(old_*)과 새로 쓸 좌표(new_lat·new_lon)를 저장한다 — 되돌리기에 쓴다."""
    spec = TABLES[plan.name]
    cols = spec["set"] + spec["fill_if_blank"] + spec["touch"]
    p = out_dir / f"backup_{plan.name}_{stamp}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([plan.key, "new_lat", "new_lon", *[f"old_{c}" for c in cols]])
        for r in plan.ok_rows():
            b = r["_before"]
            w.writerow([r[plan.key], repr(r["lat"]), repr(r["lon"]), *["" if b.get(c) is None else b.get(c) for c in cols]])
    return p


def apply_plan(plan: Plan, store: Store) -> int:
    """계획의 '반영' 행을 한 거래로 쓴다. 한 행이라도 1행이 안 바뀌면 전부 되돌리고 오류를 낸다."""
    spec = TABLES[plan.name]
    sets = [f"`{c}` = %s" for c in spec["set"]] + [f"`{c}` = COALESCE(NULLIF(`{c}`, ''), %s, `{c}`)" for c in spec["fill_if_blank"]]
    sets += [f"`{c}` = CURRENT_TIMESTAMP" for c in spec["touch"]]
    sql = f"UPDATE `{plan.table}` SET {', '.join(sets)} WHERE `{plan.key}` = %s AND {GUARD}"
    n = 0
    store.begin()
    try:
        for r in plan.ok_rows():
            args = tuple(r.get(c) for c in spec["set"] + spec["fill_if_blank"]) + (r[plan.key],)
            if store.execute(sql, args) != 1:
                raise RuntimeError(f"{plan.table} {plan.key}={r[plan.key]}: 계획과 달라서 멈춥니다(그새 값이 바뀐 것 같아요). 이 표는 아무것도 반영하지 않았습니다.")
            n += 1
        store.commit()
    except Exception:
        store.rollback()
        raise
    finally:
        store.close()
    return n


def verify_applied(plan: Plan, store: Store) -> int:
    """반영한 키 중 지금 lat·gid가 채워진 행 수 (반영 행 수와 같아야 한다)."""
    keys = [r[plan.key] for r in plan.ok_rows()]
    n = 0
    for part in _chunks(keys, CHUNK):
        n += int(store.fetch(f"SELECT COUNT(*) AS n FROM `{plan.table}` WHERE `{plan.key}` IN ({', '.join(['%s'] * len(part))}) "
                             "AND lat IS NOT NULL AND gid IS NOT NULL", tuple(part))[0]["n"])
    return n


def rollback_from_backup(name: str, backup: str | Path, store: Store, apply: bool) -> tuple[int, int]:
    """백업 CSV로 되돌린다. 지금 lat·lon이 우리가 쓴 값(new_*)과 같은 행만 되돌린다 (그 뒤에 누가 고친 행은 건드리지 않는다).
    돌려주는 값: (되돌릴 수 있는 행, 건너뛴 행)"""
    spec = TABLES[name]
    table, key, kt = spec["table"], spec["key"], spec["key_type"]
    cols = spec["set"] + spec["fill_if_blank"] + spec["touch"]
    with open(backup, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    todo, skip = [], 0
    for r in rows:
        k = kt(r[key])
        d = store.fetch(f"SELECT `lat`, `lon` FROM `{table}` WHERE `{key}` = %s", (k,))
        if d and d[0]["lat"] is not None and abs(float(d[0]["lat"]) - float(r["new_lat"])) < 1e-9 and abs(float(d[0]["lon"]) - float(r["new_lon"])) < 1e-9:
            todo.append((k, r))
        else:
            skip += 1
    if not apply:
        return len(todo), skip
    sql = f"UPDATE `{table}` SET {', '.join(f'`{c}` = %s' for c in cols)} WHERE `{key}` = %s AND lat = %s AND lon = %s"
    store.begin()
    try:
        for k, r in todo:
            args = tuple((None if r[f"old_{c}"] == "" else r[f"old_{c}"]) for c in cols) + (k, float(r["new_lat"]), float(r["new_lon"]))
            if store.execute(sql, args) != 1:
                raise RuntimeError(f"{table} {key}={k}: 되돌리는 중 1행이 안 바뀌어 멈춥니다. 아무것도 되돌리지 않았습니다.")
        store.commit()
    except Exception:
        store.rollback()
        raise
    finally:
        store.close()
    return len(todo), skip


def stamp_now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
