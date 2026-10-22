"""적재가 읽고 쓰는 DB 부분. MySQLStore는 app/core/db.py 연결로 79·80·84·01을 다루고,
MemoryStore는 시험용 가짜 DB다 (공용 DB에 쓰지 않고 시험하기 위해).

값은 항상 %s 자리표시자로 넘긴다. 칸 이름은 아래 고정 목록에서만 SQL에 넣는다.
"""
from __future__ import annotations

import copy
from datetime import date
from typing import Any, Iterable, Sequence

# 79 src_complaint 에 직접 넣는 칸 (db_first_loaded_at · db_last_updated_at 는 DB가 채움)
COMPLAINT_COLS = [
    "complaint_id", "source_receipt_no", "raw_position", "source_type", "receipt_channel", "inflow_media",
    "report_type_raw", "received_date", "processed_date", "has_processed_date", "processing_days", "request_org",
    "transfer_org", "location_text", "gu", "admin_dong_name", "lat", "lon", "gid", "coord_method", "coord_accuracy",
    "photo_cnt", "first_photo_at", "occurred_at", "reported_at", "display_tag", "masked_summary", "raw_pii_patterns",
    "dup_flag", "repeated_title", "relevance", "ped_type", "class_confidence", "class_reason", "data_period", "upload_id",
]
# C-10 재발 표시 (SQL v2.x에서 79에 더할 칸 — docs/load/ 재발표시_DB추가_제안). 칸이 없는 DB에서는 쓰지 않는다.
RECURRENCE_COLS = ["recurrence_flag", "recurrence_prev_id"]
CHANGE_COLS = ["complaint_id", "changed_column", "old_value", "new_value", "load_batch", "changed_by_type", "changed_by_user"]
_CHUNK = 500


def _chunks(seq: Sequence, n: int = _CHUNK):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class MySQLStore:
    def __init__(self, con):
        self.con = con
        self._recur: bool | None = None

    def supports_recurrence(self) -> bool:
        if self._recur is None:
            rows = self._all("SELECT COUNT(*) AS n FROM information_schema.columns WHERE table_schema = DATABASE() "
                             "AND table_name = 'src_complaint' AND column_name IN (%s, %s)", RECURRENCE_COLS)
            self._recur = int(rows[0]["n"]) == len(RECURRENCE_COLS)
        return self._recur

    def cols(self) -> list[str]:
        return COMPLAINT_COLS + (RECURRENCE_COLS if self.supports_recurrence() else [])

    def find_priors(self, gids: Sequence[str]) -> list[dict]:
        """재발 판단용: 이 칸들에서 처리가 끝난(처리일이 있는) 지난 민원."""
        out: list[dict] = []
        for part in _chunks(sorted(set(gids))):
            marks = ", ".join(["%s"] * len(part))
            out += self._all("SELECT complaint_id, gid, report_type_raw, ped_type, processed_date FROM src_complaint "
                             f"WHERE gid IN ({marks}) AND processed_date IS NOT NULL "
                             "AND (ped_type IS NOT NULL OR report_type_raw IS NOT NULL)", part)
        return out

    # --- 거래 ---
    def commit(self) -> None:
        self.con.commit()

    def rollback(self) -> None:
        self.con.rollback()

    def _all(self, sql: str, args: Sequence[Any] = ()) -> list[dict]:
        with self.con.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())

    # --- 읽기 ---
    def grid_rows(self) -> list[tuple]:
        rows = self._all("SELECT gid, center_lat, center_lon, gu_center, admin_dong_center FROM grid_cell")
        return [(r["gid"], r["center_lat"], r["center_lon"], r["gu_center"], r["admin_dong_center"]) for r in rows]

    def recurrence_rows(self) -> list[dict]:
        """재발 다시 계산용: 격자가 있거나 재발 표시가 이미 있는 모든 민원의 필요한 칸만 (원문 없음)."""
        return self._all("SELECT complaint_id, gid, report_type_raw, ped_type, received_date, processed_date, "
                         "recurrence_flag, recurrence_prev_id FROM src_complaint WHERE gid IS NOT NULL OR recurrence_flag IS NOT NULL")

    def get_existing(self, ids: Sequence[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        cols = ", ".join(self.cols())
        for part in _chunks(list(ids)):
            marks = ", ".join(["%s"] * len(part))
            for r in self._all(f"SELECT {cols} FROM src_complaint WHERE complaint_id IN ({marks})", part):
                out[r["complaint_id"]] = r
        return out

    def receipt_owners(self, receipts: Sequence[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in _chunks(list(receipts)):
            marks = ", ".join(["%s"] * len(part))
            for r in self._all(f"SELECT source_receipt_no, complaint_id FROM src_complaint WHERE source_receipt_no IN ({marks})", part):
                out[r["source_receipt_no"]] = r["complaint_id"]
        return out

    def count_missing(self, start: date, end: date, ids: Sequence[str]) -> int:
        """빠짐: DB에는 있는데(그 기간 접수) 새 파일에는 없는 민원 수."""
        keep = set(ids)
        rows = self._all("SELECT complaint_id FROM src_complaint WHERE received_date BETWEEN %s AND %s", (start, end))
        return sum(1 for r in rows if r["complaint_id"] not in keep)

    def count_rows(self) -> int:
        return int(self._all("SELECT COUNT(*) AS n FROM src_complaint")[0]["n"])

    def list_uploads(self, limit: int) -> list[dict]:
        """AD-03 '올린 기록': 84 data_upload 최신 순 (올린 운영자 이름은 60 app_user에서)."""
        return self._all(
            "SELECT u.upload_id, u.data_name, u.file_name, u.source, u.ref_date, u.period_start, u.period_end, "
            "u.is_official_raw, u.uploaded_by, a.display_name AS uploaded_by_name, u.uploaded_at, u.check_result, "
            "u.row_cnt, u.remark FROM data_upload u LEFT JOIN app_user a ON a.user_id = u.uploaded_by "
            "ORDER BY u.uploaded_at DESC, u.upload_id DESC LIMIT %s", (int(limit),))

    # --- 쓰기 ---
    def create_upload(self, meta, file_name: str) -> int:
        with self.con.cursor() as cur:
            cur.execute(
                "INSERT INTO data_upload (data_name, file_name, source, ref_date, period_start, period_end, is_official_raw, uploaded_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (meta.data_name, file_name, meta.source, meta.ref_date, meta.period_start, meta.period_end,
                 meta.is_official_raw, meta.uploaded_by))
            return int(cur.lastrowid)

    def finish_upload(self, upload_id: int, check_result: str, row_cnt: int | None, remark: str | None) -> None:
        with self.con.cursor() as cur:
            cur.execute("UPDATE data_upload SET check_result = %s, row_cnt = %s, remark = %s WHERE upload_id = %s",
                        (check_result[:300], row_cnt, remark[:500] if remark else None, upload_id))

    def insert_complaints(self, records: Sequence[dict]) -> None:
        names = self.cols()
        cols = ", ".join(names)
        marks = ", ".join(["%s"] * len(names))
        recur = "recurrence_prev_id" in names
        with self.con.cursor() as cur:
            for part in _chunks(list(records)):
                # recurrence_prev_id는 같은 파일의 아직 안 들어간 민원을 가리킬 수 있어(외래키), 모두 넣은 뒤에 채운다
                cur.executemany(f"INSERT INTO src_complaint ({cols}) VALUES ({marks})",
                                [tuple(None if c == "recurrence_prev_id" else r.get(c) for c in names) for r in part])
            if recur:
                links = [(r["recurrence_prev_id"], r["complaint_id"]) for r in records if r.get("recurrence_prev_id")]
                for part in _chunks(links):
                    cur.executemany("UPDATE src_complaint SET recurrence_prev_id = %s WHERE complaint_id = %s", part)

    def update_complaint(self, complaint_id: str, values: dict, touch: bool) -> None:
        assert set(values) <= set(self.cols()), "알 수 없는 칸"
        sets = [f"{c} = %s" for c in values] + (["db_last_updated_at = NOW()"] if touch else [])
        with self.con.cursor() as cur:
            cur.execute(f"UPDATE src_complaint SET {', '.join(sets)} WHERE complaint_id = %s", (*values.values(), complaint_id))

    def insert_changes(self, rows: Sequence[dict]) -> None:
        cols = ", ".join(CHANGE_COLS)
        marks = ", ".join(["%s"] * len(CHANGE_COLS))
        with self.con.cursor() as cur:
            for part in _chunks(list(rows)):
                cur.executemany(f"INSERT INTO src_complaint_change ({cols}) VALUES ({marks})",
                                [tuple(r.get(c) for c in CHANGE_COLS) for r in part])


class MemoryStore:
    """시험용 가짜 DB. commit 때 상태를 저장하고 rollback 때 되돌린다."""

    def __init__(self, grid_rows: Iterable[tuple] = (), fail_on_change_insert: bool = False, recurrence: bool = True):
        self._grid = list(grid_rows)
        self._recur = recurrence
        self.complaints: dict[str, dict] = {}
        self.changes: list[dict] = []
        self.uploads: dict[int, dict] = {}
        self.fail_on_change_insert = fail_on_change_insert
        self._snap = self._snapshot()

    def _snapshot(self):
        return copy.deepcopy((self.complaints, self.changes, self.uploads))

    def commit(self) -> None:
        self._snap = self._snapshot()

    def rollback(self) -> None:
        self.complaints, self.changes, self.uploads = copy.deepcopy(self._snap)

    def grid_rows(self):
        return list(self._grid)

    def supports_recurrence(self):
        return self._recur

    def cols(self):
        return COMPLAINT_COLS + (RECURRENCE_COLS if self._recur else [])

    def recurrence_rows(self):
        return [dict(r, complaint_id=i) for i, r in self.complaints.items() if r.get("gid") or r.get("recurrence_flag")]

    def find_priors(self, gids):
        want = set(gids)
        return [dict(complaint_id=i, gid=r["gid"], report_type_raw=r["report_type_raw"], ped_type=r.get("ped_type"),
                     processed_date=r["processed_date"])
                for i, r in self.complaints.items()
                if r.get("gid") in want and r.get("processed_date") and (r.get("report_type_raw") or r.get("ped_type"))]

    def get_existing(self, ids):
        return {i: dict(self.complaints[i]) for i in ids if i in self.complaints}

    def receipt_owners(self, receipts):
        want = set(receipts)
        return {r["source_receipt_no"]: i for i, r in self.complaints.items() if r.get("source_receipt_no") in want}

    def count_missing(self, start, end, ids):
        keep = set(ids)
        return sum(1 for i, r in self.complaints.items()
                   if i not in keep and r.get("received_date") and start.isoformat() <= str(r["received_date"])[:10] <= end.isoformat())

    def count_rows(self):
        return len(self.complaints)

    def list_uploads(self, limit):
        rows = sorted(self.uploads.values(), key=lambda u: -u["upload_id"])[:limit]
        return [dict(u, uploaded_by_name=None, uploaded_at=None) for u in rows]

    def create_upload(self, meta, file_name):
        uid = max(self.uploads, default=0) + 1
        self.uploads[uid] = dict(upload_id=uid, data_name=meta.data_name, file_name=file_name, source=meta.source,
                                 ref_date=meta.ref_date, period_start=meta.period_start, period_end=meta.period_end,
                                 is_official_raw=meta.is_official_raw, uploaded_by=meta.uploaded_by,
                                 check_result=None, row_cnt=None, remark=None)
        return uid

    def finish_upload(self, upload_id, check_result, row_cnt, remark):
        self.uploads[upload_id].update(check_result=check_result[:300], row_cnt=row_cnt, remark=remark[:500] if remark else None)

    def _check_fk(self, prev):
        if prev is not None and prev not in self.complaints:
            raise ValueError("FK 위반: recurrence_prev_id")               # MySQL 외래키처럼 그 시점에 이미 있어야 한다

    def insert_complaints(self, records):
        """MySQLStore와 같이 두 단계: 먼저 recurrence_prev_id 없이 넣고, 나중에 채운다 (같은 파일 안 민원을 가리킬 수 있어서)."""
        for r in records:
            if r["complaint_id"] in self.complaints:
                raise ValueError("중복 키")
            row = {c: r.get(c) for c in self.cols()} | {"touched": 0}
            row["recurrence_prev_id"] = None if self._recur else row.get("recurrence_prev_id")
            self.complaints[r["complaint_id"]] = row
        if self._recur:
            for r in records:
                self._check_fk(r.get("recurrence_prev_id"))
                self.complaints[r["complaint_id"]]["recurrence_prev_id"] = r.get("recurrence_prev_id")

    def update_complaint(self, complaint_id, values, touch):
        self._check_fk(values.get("recurrence_prev_id"))
        self.complaints[complaint_id].update(values)
        if touch:
            self.complaints[complaint_id]["touched"] = self.complaints[complaint_id].get("touched", 0) + 1

    def insert_changes(self, rows):
        if self.fail_on_change_insert:
            raise RuntimeError("시험용 실패")
        self.changes.extend({c: r.get(c) for c in CHANGE_COLS} for r in rows)
