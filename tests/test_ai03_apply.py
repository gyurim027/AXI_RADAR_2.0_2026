"""AI-03 좌표 반영 시험 — 실제 DB 없이 sqlite로 돈다 (표 구조는 SQL v2.3의 좌표 칸만 흉내). 시험 값은 모두 가짜."""
import csv
import sqlite3

import pytest

from app.services.ai03 import apply_updates as A


class SqliteStore:
    def __init__(self, con, limits=None):
        self.con, self.limits = con, limits or {}

    def fetch(self, sql, args=()):
        cur = self.con.execute(sql.replace("%s", "?"), args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def column_limits(self, table, cols):
        return {c: n for c, n in self.limits.items() if c in set(cols)}

    def begin(self):
        pass

    def execute(self, sql, args=()):
        return self.con.execute(sql.replace("%s", "?"), args).rowcount

    def commit(self):
        self.con.commit()

    def rollback(self):
        self.con.rollback()

    def close(self):
        pass


GEO = "lat REAL, lon REAL, gid TEXT, grid_no TEXT, gu_by_coord TEXT, admin_dong_by_coord TEXT, coord_method TEXT, coord_accuracy TEXT"


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE grid_cell (gid TEXT PRIMARY KEY)")
    con.executemany("INSERT INTO grid_cell VALUES (?)", [("G1",), ("G2",), ("G3",)])
    con.execute(f"CREATE TABLE src_parking_enforce_place (row_id INTEGER PRIMARY KEY, enforce_cnt INTEGER, {GEO})")
    con.executemany("INSERT INTO src_parking_enforce_place (row_id, enforce_cnt, coord_method) VALUES (?, 5, ?)",
                    [(1, "찾지 못함"), (2, "찾지 못함"), (3, "찾지 못함"), (4, "찾지 못함")])
    con.execute("UPDATE src_parking_enforce_place SET lat = 37.4, lon = 127.1, gid = 'G1' WHERE row_id = 4")   # 이미 좌표 있음
    con.execute("CREATE TABLE src_complaint (complaint_id TEXT PRIMARY KEY, gu TEXT, admin_dong_name TEXT, lat REAL, lon REAL, gid TEXT, coord_method TEXT, coord_accuracy TEXT, db_last_updated_at TEXT DEFAULT '2020-01-01 00:00:00')")
    con.executemany("INSERT INTO src_complaint (complaint_id, gu, admin_dong_name, coord_method) VALUES (?, ?, ?, '주소 변환(못 찾음)')",
                    [("C-T1", "분당구", None), ("C-T2", None, None)])
    con.commit()
    return con


def write(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


P_HEAD = ["row_id", "lat", "lon", "gid", "grid_no", "gu_by_coord", "admin_dong_by_coord", "coord_method", "coord_accuracy", "review_result"]


def p_row(k, lat="37.35", lon="127.11", gid="G2", method="AI-03 시험"):
    return [k, lat, lon, gid, "G-1", "분당구", "시험동", method, "낮음 (시험)", "맞음"]


@pytest.fixture(autouse=True)
def no_pyproj(monkeypatch):
    monkeypatch.setattr(A, "_gid_from_coord", lambda lat, lon: None)      # 좌표→gid 검사는 따로 시험


def test_plan_statuses(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1), p_row(999), p_row(4), p_row(2, gid="NOPE"), p_row(3, lat="abc"), p_row(1)])
    plan = A.build_plan("parking", f, SqliteStore(db))
    assert plan.summary() == {A.OK: 1, A.MISSING: 1, A.HAS_COORD: 1, A.NO_GRID: 1, A.BAD_VALUE: 1, A.DUP_KEY: 1}


def test_review_result_column_is_ignored_and_missing_column_stops(tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1)])
    assert "review_result" not in A.read_update_file("parking", f)[0]
    g = write(tmp_path / "v.csv", ["row_id", "lat"], [[1, 37.3]])
    with pytest.raises(ValueError, match="필요한 칸이 없습니다"):
        A.read_update_file("parking", g)


def test_too_long_value_is_blocked(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1, method="아주 긴 좌표 방법 이름")])
    plan = A.build_plan("parking", f, SqliteStore(db, limits={"coord_method": 5}))
    assert plan.summary() == {A.TOO_LONG: 1}


def test_gid_mismatch_is_blocked(db, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_gid_from_coord", lambda lat, lon: "G3")
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1, gid="G2")])
    assert A.build_plan("parking", f, SqliteStore(db)).summary() == {A.GID_MISMATCH: 1}


def test_coordinate_outside_grid_is_blocked(db, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_gid_from_coord", lambda lat, lon: A.OUTSIDE)
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1, gid="G2")])
    assert A.build_plan("parking", f, SqliteStore(db)).summary() == {A.GID_MISMATCH: 1}


def test_preview_does_not_write(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1)])
    A.build_plan("parking", f, SqliteStore(db))
    assert db.execute("SELECT lat FROM src_parking_enforce_place WHERE row_id = 1").fetchone()[0] is None


def test_apply_writes_only_blank_rows_and_makes_backup(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1), p_row(2, lat="37.36"), p_row(4)])
    store = SqliteStore(db)
    plan = A.build_plan("parking", f, store)
    backup = A.write_backup(plan, tmp_path, "t1")
    assert A.apply_plan(plan, store) == 2 and A.verify_applied(plan, store) == 2
    rows = {r[0]: r[1:] for r in db.execute("SELECT row_id, lat, gid, coord_method FROM src_parking_enforce_place")}
    assert rows[1] == (37.35, "G2", "AI-03 시험") and rows[2][0] == 37.36
    assert rows[4] == (37.4, "G1", "찾지 못함")                        # 이미 좌표가 있던 행은 그대로
    assert rows[3][0] is None                                           # 파일에 없는 행도 그대로
    text = backup.read_text(encoding="utf-8-sig")
    assert "old_coord_method" in text and "찾지 못함" in text and "37.35" in text


def test_apply_rolls_back_everything_if_a_row_changed_meanwhile(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1), p_row(2), p_row(3)])
    store = SqliteStore(db)
    plan = A.build_plan("parking", f, store)
    db.execute("UPDATE src_parking_enforce_place SET lat = 37.5, lon = 127.2, gid = 'G3' WHERE row_id = 3")   # 계획 뒤에 누가 고침
    db.commit()
    with pytest.raises(RuntimeError, match="계획과 달라서"):
        A.apply_plan(plan, store)
    left = [r[0] for r in db.execute("SELECT lat FROM src_parking_enforce_place WHERE row_id IN (1, 2)")]
    assert left == [None, None]                                         # 1·2번도 반영되지 않았다


def test_complaint_fills_gu_and_dong_only_when_blank(db, tmp_path):
    head = ["complaint_id", "lat", "lon", "gid", "gu", "admin_dong_name", "coord_method", "coord_accuracy", "review_result"]
    f = write(tmp_path / "c.csv", head, [["C-T1", 37.35, 127.1, "G1", "수정구", "시험동", "주소 다듬기(장소 이름 검색)", "낮음", "맞음"],
                                         ["C-T2", 37.36, 127.1, "G2", "중원구", "시험동2", "주소 다듬기(장소 이름 검색)", "낮음", "맞음"]])
    store = SqliteStore(db)
    plan = A.build_plan("complaint", f, store)
    assert A.apply_plan(plan, store) == 2
    got = {r[0]: r[1:] for r in db.execute("SELECT complaint_id, gu, admin_dong_name, lat FROM src_complaint")}
    assert got["C-T1"] == ("분당구", "시험동", 37.35)                    # 원래 구(분당구)는 덮어쓰지 않고, 빈 동만 채움
    assert got["C-T2"] == ("중원구", "시험동2", 37.36)
    assert all(r[0] != "2020-01-01 00:00:00" for r in db.execute("SELECT db_last_updated_at FROM src_complaint"))   # 값을 바꾼 시각은 지금으로


def test_complaint_rollback_restores_old_update_time_and_blank_fields(db, tmp_path):
    head = ["complaint_id", "lat", "lon", "gid", "gu", "admin_dong_name", "coord_method", "coord_accuracy"]
    f = write(tmp_path / "c.csv", head, [["C-T1", 37.35, 127.1, "G1", "수정구", "시험동", "주소 다듬기(장소 이름 검색)", "낮음"]])
    store = SqliteStore(db)
    plan = A.build_plan("complaint", f, store)
    backup = A.write_backup(plan, tmp_path, "t3")
    A.apply_plan(plan, store)
    assert A.rollback_from_backup("complaint", backup, store, apply=True) == (1, 0)
    r = db.execute("SELECT gu, admin_dong_name, lat, coord_method, db_last_updated_at FROM src_complaint WHERE complaint_id = 'C-T1'").fetchone()
    assert r == ("분당구", None, None, "주소 변환(못 찾음)", "2020-01-01 00:00:00")


def test_rollback_restores_and_skips_rows_changed_after(db, tmp_path):
    f = write(tmp_path / "u.csv", P_HEAD, [p_row(1), p_row(2), p_row(3)])
    store = SqliteStore(db)
    plan = A.build_plan("parking", f, store)
    backup = A.write_backup(plan, tmp_path, "t2")
    A.apply_plan(plan, store)
    db.execute("UPDATE src_parking_enforce_place SET lat = 37.45 WHERE row_id = 3")     # 반영 뒤에 누가 또 고친 행
    db.commit()
    assert A.rollback_from_backup("parking", backup, store, apply=False) == (2, 1)       # 미리 보기: 2행 되돌림, 1행 건너뜀
    assert db.execute("SELECT lat FROM src_parking_enforce_place WHERE row_id = 1").fetchone()[0] == 37.35
    assert A.rollback_from_backup("parking", backup, store, apply=True) == (2, 1)
    r = {x[0]: x[1:] for x in db.execute("SELECT row_id, lat, gid, coord_method FROM src_parking_enforce_place")}
    assert r[1] == (None, None, "찾지 못함") and r[2] == (None, None, "찾지 못함")        # 원래 값으로
    assert r[3][0] == 37.45                                                              # 나중에 바뀐 행은 그대로
