"""A-06·A-08 → data_issue 적재 시험 — 실제 DB 없이 sqlite로 돈다. 시험 값은 모두 가짜."""
import csv
import sqlite3

import pytest

from app.services.quality import issue_load as L

HEAD = ["check_fn", "error_code", "검사", "표", "행 키", "칸", "값", "사유", "묶음 ID", "원본 파일", "원본 행 번호",
        "upload_id", "찾은 시각", "확인", "처리"]


class SqliteStore:
    def __init__(self, con):
        self.con = con

    def fetch(self, sql, args=()):
        cur = self.con.execute(sql.replace("%s", "?"), args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

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


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE data_upload (upload_id INTEGER PRIMARY KEY)")
    con.execute("INSERT INTO data_upload VALUES (1)")
    con.execute("""CREATE TABLE data_issue (issue_id INTEGER PRIMARY KEY AUTOINCREMENT, check_fn TEXT NOT NULL, error_code TEXT NOT NULL,
        check_name TEXT NOT NULL, table_name TEXT NOT NULL DEFAULT '', row_key TEXT NOT NULL DEFAULT '', field_name TEXT NOT NULL DEFAULT '',
        value_text TEXT, reason TEXT, group_id TEXT, source_file TEXT NOT NULL DEFAULT '', source_row_no INTEGER NOT NULL DEFAULT 0,
        upload_id INTEGER, job_run_id INTEGER, found_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, review_status TEXT, resolution TEXT,
        UNIQUE (check_fn, error_code, table_name, row_key, field_name, source_file, source_row_no))""")
    con.commit()
    return con


def row(key="complaint_id=C-T1", code="A06_OUT_OF_GRID", fn="A-06", val="37.1,127.0", upload="", rowno="", src=""):
    return [fn, code, "성남 격자 밖", "src_complaint", key, "lat;lon", val, "시험", "", src, rowno, upload, "2026-10-26T17:30:00", "", ""]


def write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    return path


def test_blank_cells_become_empty_text_and_zero(tmp_path):
    f = write(tmp_path / "a.csv", [["A-06", "A06_X", "시험", "", "", "", "", "", "", "", "", "", "", "", ""]])
    r = L.read_issue_file(f)[0]
    assert (r["table_name"], r["row_key"], r["field_name"], r["source_file"], r["source_row_no"]) == ("", "", "", "", 0)
    assert r["upload_id"] is None and r["value_text"] is None and len(r["found_at"]) == 19


def test_only_a06_a08_and_missing_columns_stop(tmp_path, db):
    f = write(tmp_path / "a.csv", [row()])
    with pytest.raises(ValueError, match="A-05는 진이님"):
        L.build_plan("A-05", f, SqliteStore(db))
    with open(tmp_path / "b.csv", "w", encoding="utf-8-sig", newline="") as g:
        csv.writer(g).writerow(["check_fn", "error_code"])
    with pytest.raises(ValueError, match="필요한 칸이 없습니다"):
        L.build_plan("A-06", tmp_path / "b.csv", SqliteStore(db))


def test_plan_statuses(db, tmp_path):
    f = write(tmp_path / "a.csv", [row("complaint_id=C-1"), row("complaint_id=C-1"), row("complaint_id=C-2", fn="A-08", code="A08_SAME_CONTENT"),
                                  row("complaint_id=C-3", code="A08_SAME_CONTENT"), row("x" * 201), row("complaint_id=C-4", upload="99"),
                                  row("complaint_id=C-5", upload="1", rowno="12.0")])
    s = L.build_plan("A-06", f, SqliteStore(db)).summary()
    assert s == {L.NEW: 2, L.DUP_KEY: 1, L.BAD_FN: 1, L.BAD_CODE: 1, L.TOO_LONG: 1, L.NO_UPLOAD: 1}


def test_apply_inserts_and_leaves_operator_columns_empty(db, tmp_path):
    f = write(tmp_path / "a.csv", [row("complaint_id=C-1"), row("complaint_id=C-2", rowno="5", src="2026 파일")])
    store = SqliteStore(db)
    plan = L.build_plan("A-06", f, store)
    assert L.apply_plan(plan, store, job_run_id=7) == (2, 0, 0) and L.verify(plan, store) == 2
    got = db.execute("SELECT row_key, source_file, source_row_no, review_status, job_run_id FROM data_issue ORDER BY row_key").fetchall()
    assert got == [("complaint_id=C-1", "", 0, None, 7), ("complaint_id=C-2", "2026 파일", 5, None, 7)]


def test_rerun_updates_values_but_never_the_operator_columns(db, tmp_path):
    store = SqliteStore(db)
    f1 = write(tmp_path / "a.csv", [row("complaint_id=C-1", val="v1"), row("complaint_id=C-2")])
    L.apply_plan(L.build_plan("A-06", f1, store), store)
    db.execute("UPDATE data_issue SET review_status = '확인함', resolution = '원본 오류' WHERE row_key = 'complaint_id=C-1'")
    db.commit()
    f2 = write(tmp_path / "b.csv", [row("complaint_id=C-1", val="v2"), row("complaint_id=C-2")])
    plan = L.build_plan("A-06", f2, store)
    assert plan.summary() == {L.CHANGED: 1, L.SAME: 1}
    assert L.apply_plan(plan, store) == (0, 2, 0)
    r = db.execute("SELECT value_text, review_status, resolution FROM data_issue WHERE row_key = 'complaint_id=C-1'").fetchone()
    assert r == ("v2", "확인함", "원본 오류")                                 # 값은 바뀌고, 운영자 칸은 그대로
    assert db.execute("SELECT COUNT(*) FROM data_issue").fetchone()[0] == 2    # 같은 문제는 한 줄


def test_lines_missing_from_new_run_are_reported_not_deleted(db, tmp_path):
    store = SqliteStore(db)
    L.apply_plan(L.build_plan("A-06", write(tmp_path / "a.csv", [row("complaint_id=C-1"), row("complaint_id=C-2")]), store), store)
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)
    assert len(plan.stale) == 1 and plan.stale[0]["row_key"] == "complaint_id=C-2"
    L.apply_plan(plan, store)
    assert db.execute("SELECT COUNT(*) FROM data_issue").fetchone()[0] == 2    # 지우지 않았다


def test_apply_is_all_or_nothing(db, tmp_path):
    store = SqliteStore(db)
    plan = L.build_plan("A-06", write(tmp_path / "a.csv", [row("complaint_id=C-1"), row("complaint_id=C-2")]), store)
    db.execute("INSERT INTO data_issue (check_fn, error_code, check_name, table_name, row_key, field_name) VALUES "
               "('A-06', 'A06_OUT_OF_GRID', '시험', 'src_complaint', 'complaint_id=C-2', 'lat;lon')")   # 계획 뒤에 누가 같은 줄을 넣음
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        L.apply_plan(plan, store)
    assert db.execute("SELECT COUNT(*) FROM data_issue").fetchone()[0] == 1    # C-1도 들어가지 않았다


def test_rollback_deletes_new_restores_updated_and_spares_reviewed(db, tmp_path):
    store = SqliteStore(db)
    L.apply_plan(L.build_plan("A-06", write(tmp_path / "a.csv", [row("complaint_id=C-1", val="v1")]), store), store)
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1", val="v2"), row("complaint_id=C-2"), row("complaint_id=C-3")]), store)
    backup = L.write_backup(plan, tmp_path, "t")
    L.apply_plan(plan, store)
    db.execute("UPDATE data_issue SET review_status = '확인함' WHERE row_key = 'complaint_id=C-3'")        # 그 뒤에 운영자가 확인
    db.commit()
    assert L.rollback_from_backup("A-06", backup, store, apply=False) == (1, 1, 0, 1)
    assert L.rollback_from_backup("A-06", backup, store, apply=True) == (1, 1, 0, 1)
    got = dict(db.execute("SELECT row_key, value_text FROM data_issue").fetchall())
    assert got == {"complaint_id=C-1": "v1", "complaint_id=C-3": "37.1,127.0"}   # C-1 옛 값 복원, C-2 삭제, 확인된 C-3은 유지


def test_exclude_skips_the_asked_table_and_check(db, tmp_path):
    def r8(table, check, key):
        return ["A-08", "A08_SAME_SPOT_DIFF_NAME", check, table, key, "", "이름", "대표", "G-1", "", "", "", "2026-10-26T17:30:00", "", ""]
    f = write(tmp_path / "a.csv", [r8("src_parking_enforce_place", "③ 같은 자리·다른 이름 (확인 필요)", "row_id=1"),
                                  r8("src_parking_enforce_place", "③ 같은 자리·다른 이름 (확인 필요)", "row_id=2"),
                                  r8("src_crosswalk", "③ 같은 자리·다른 이름 (확인 필요)", "crosswalk_id=7")])
    store = SqliteStore(db)
    plan = L.build_plan("A-08", f, store, exclude=[("src_parking_enforce_place", "③")])
    assert plan.summary() == {L.EXCLUDED: 2, L.NEW: 1}
    assert L.apply_plan(plan, store) == (1, 0, 0)
    assert [r[0] for r in db.execute("SELECT table_name FROM data_issue")] == ["src_crosswalk"]


# ── 정리(--prune-stale) ─────────────────────────────────────────────────────────
def load(db, tmp_path, rows, name="a.csv"):
    store = SqliteStore(db)
    L.apply_plan(L.build_plan("A-06", write(tmp_path / name, rows), store), store)
    return store


def keys(db, fn="A-06"):
    return {r[0] for r in db.execute("SELECT row_key FROM data_issue WHERE check_fn = ?", (fn,))}


def test_prune_deletes_only_unreviewed_stale_rows_of_the_same_check(db, tmp_path):
    store = load(db, tmp_path, [row("complaint_id=C-1"), row("complaint_id=C-2"), row("complaint_id=C-3")])
    db.execute("UPDATE data_issue SET review_status = '확인함' WHERE row_key = 'complaint_id=C-2'")      # 운영자가 확인함
    db.execute("INSERT INTO data_issue (check_fn, error_code, check_name, table_name, row_key, field_name) "
               "VALUES ('A-05', 'A05_X', '시험', 't', 'k', 'f')")                                       # 진이님 줄
    db.commit()
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)
    assert len(plan.stale) == 2 and len(L.prunable(plan)) == 1 and len(L.kept_stale(plan)) == 1
    lst = L.write_stale_csv(plan, tmp_path, "t", prune=True).read_text(encoding="utf-8-sig")
    assert "지움(--prune-stale)" in lst and "남김(운영자 칸 있음)" in lst
    assert L.apply_plan(plan, store, prune=True) == (0, 1, 1)
    assert keys(db) == {"complaint_id=C-1", "complaint_id=C-2"}                                      # 확인된 C-2는 남았다
    assert db.execute("SELECT COUNT(*) FROM data_issue WHERE check_fn = 'A-05'").fetchone()[0] == 1  # A-05는 안 건드림


def test_nothing_is_deleted_unless_prune_is_asked(db, tmp_path):
    store = load(db, tmp_path, [row("complaint_id=C-1"), row("complaint_id=C-2")])
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)
    assert L.apply_plan(plan, store) == (0, 1, 0)
    assert keys(db) == {"complaint_id=C-1", "complaint_id=C-2"}


def test_prune_stops_when_it_would_delete_too_much(db, tmp_path):
    db.executemany("INSERT INTO data_issue (check_fn, error_code, check_name, table_name, row_key, field_name) "
                   "VALUES ('A-06', 'A06_OUT_OF_GRID', '시험', 'src_complaint', ?, 'lat;lon')", [(f"complaint_id=X{i}",) for i in range(200)])
    db.commit()
    store = SqliteStore(db)
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)    # 파일을 잘못 줬다고 치자
    assert plan.n_existing == 200 and len(L.prunable(plan)) == 200 and L.prune_limit(200) == 50
    with pytest.raises(ValueError, match="상한"):
        L.check_prune(plan)
    with pytest.raises(ValueError, match="상한"):
        L.apply_plan(plan, store, prune=True)
    assert len(keys(db)) == 200                                       # 아무것도 안 바뀜
    L.check_prune(plan, prune_max=300)                               # 파일이 맞다고 확인하고 올리면 통과


def test_rows_that_are_in_the_file_but_excluded_are_not_stale(db, tmp_path):
    store = load(db, tmp_path, [row("complaint_id=C-1")])
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store, exclude=[("src_complaint", "성남")])
    assert plan.summary() == {L.EXCLUDED: 1} and plan.stale == []      # 일부러 뺀 줄을 '안 나온 줄'로 보고 지우지 않는다


def test_prune_is_part_of_the_same_transaction(db, tmp_path):
    store = load(db, tmp_path, [row("complaint_id=C-9")])
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)       # C-1 새로, C-9 정리 대상
    db.execute("UPDATE data_issue SET review_status = '확인함' WHERE row_key = 'complaint_id=C-9'")  # 계획 뒤에 운영자가 확인함
    db.commit()
    with pytest.raises(RuntimeError, match="지우지 못했습니다"):
        L.apply_plan(plan, store, prune=True)
    assert keys(db) == {"complaint_id=C-9"}                            # C-1을 넣은 것도 되돌려졌다


def test_prune_backup_and_rollback_restore_deleted_rows_with_original_id(db, tmp_path):
    store = load(db, tmp_path, [row("complaint_id=C-1"), row("complaint_id=C-2")])
    ids = dict(db.execute("SELECT row_key, issue_id FROM data_issue").fetchall())
    plan = L.build_plan("A-06", write(tmp_path / "b.csv", [row("complaint_id=C-1")]), store)
    backup = L.write_backup(plan, tmp_path, "t", prune=True)
    assert L.apply_plan(plan, store, prune=True) == (0, 1, 1) and keys(db) == {"complaint_id=C-1"}
    assert L.rollback_from_backup("A-06", backup, store, apply=False) == (0, 1, 1, 0)      # 되살릴 줄 1
    assert L.rollback_from_backup("A-06", backup, store, apply=True) == (0, 1, 1, 0)
    got = dict(db.execute("SELECT row_key, issue_id FROM data_issue").fetchall())
    assert got == ids                                                                         # 원래 번호 그대로
    assert db.execute("SELECT review_status, resolution FROM data_issue WHERE row_key = 'complaint_id=C-2'").fetchone() == (None, None)
    assert L.rollback_from_backup("A-06", backup, store, apply=False) == (0, 1, 0, 1)      # 다시 하면 이미 있어서 건너뜀
