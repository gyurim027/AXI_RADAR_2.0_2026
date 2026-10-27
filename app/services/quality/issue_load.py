"""A-06·A-08 결과를 data_issue(92, SQL v2.3)에 넣는다 (세은). 입력은 quality_anomaly·quality_same_facility가 만든 공통 15칸 CSV.

원칙 (공용 DB를 고치는 일이라 조심한다)
- 미리 보기가 기본이다. --apply를 줘야만 쓴다. 미리 보기는 DB도 job_run도 안 바꾼다.
- 내 줄만 넣는다: 검사 기능(A-06 또는 A-08)을 지정하고, 파일 안의 check_fn·오류 코드가 그와 다르면 막는다.
  A-05는 진이님이 넣는다 — 이 도구로는 넣지 않는다 (서로 줄은 안 건드리기로 함).
- 같은 문제는 한 줄: (check_fn, error_code, table_name, row_key, field_name, source_file, source_row_no)가 같으면 같은 줄.
  키 칸은 NULL 대신 글자는 빈 글자, source_row_no는 0 (UNIQUE가 NULL끼리는 막지 못해서).
- 이미 있는 줄은 찾은 시각·값·사유·묶음 ID·실행 번호만 고친다. 운영자 칸(review_status·resolution)은 절대 덮어쓰지 않는다.
- 빼고 넣기: exclude로 (표, 검사 이름 앞부분)을 주면 그 줄은 넣지 않는다 (예: 좌표가 한 점에 모여 생긴 A-08 ③). 미리 보기에 '제외(요청)' 건수로 남는다.
- 지우지 않는다(기본). 이번 검사에 안 나온 기존 줄(해결됐을 수 있음)은 건수만 알려 준다 — 운영자가 처리 여부를 정한다.
- 정리(prune): 옵션을 줄 때만, 이번 검사 파일에 아예 없고 운영자 칸(확인·처리)이 비어 있는 같은 검사 기능의 기존 줄을 지운다.
  운영자 칸이 있는 줄, 다른 검사 기능(A-05)의 줄, 파일에는 있는데 exclude로 뺀 줄은 지우지 않는다.
  한 번에 너무 많이 지우려 하면(기존 줄의 10% · 최소 50줄) prune_max를 주기 전에는 멈춘다.
  지우는 줄은 백업 CSV에 전부 남겨 --rollback으로 원래 번호(issue_id) 그대로 되살린다.
- 한 거래로 쓴다: 한 줄이라도 막히면 전부 되돌리고 멈춘다. 반영 전 백업 CSV를 만들어 --rollback으로 되돌릴 수 있다.
- 값은 항상 %s 자리표시자로 넘긴다.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

# 공통 15칸(CSV 머리글) → data_issue 칸
MAP = {"check_fn": "check_fn", "error_code": "error_code", "검사": "check_name", "표": "table_name", "행 키": "row_key",
       "칸": "field_name", "값": "value_text", "사유": "reason", "묶음 ID": "group_id", "원본 파일": "source_file",
       "원본 행 번호": "source_row_no", "upload_id": "upload_id", "찾은 시각": "found_at", "확인": "review_status", "처리": "resolution"}
KEY_COLS = ["check_fn", "error_code", "table_name", "row_key", "field_name", "source_file", "source_row_no"]
TEXT_KEY = ["table_name", "row_key", "field_name", "source_file"]            # 빈 글자로
UPDATE_COLS = ["value_text", "reason", "group_id", "found_at", "job_run_id"]  # 다시 돌릴 때 고치는 칸 (운영자 칸은 제외)
LIMITS = {"check_fn": 8, "error_code": 40, "check_name": 120, "table_name": 80, "row_key": 200, "field_name": 120,
          "value_text": 500, "reason": 500, "group_id": 200, "source_file": 200, "review_status": 20, "resolution": 255}
MINE = ("A-06", "A-08")

NEW, SAME, CHANGED = "새로", "다시 확인(같은 값)", "값 바뀜"
BAD_FN, BAD_CODE, TOO_LONG, DUP_KEY, NO_UPLOAD, BAD_ROW = (
    "check_fn 다름", "오류 코드 이상", "칸 길이 초과", "키 중복", "upload_id 없음", "값 이상")
EXCLUDED = "제외(요청)"
OKS = (NEW, SAME, CHANGED)
OK_PENDING = "(확인 중)"
PRUNE_RATE, PRUNE_MIN = 0.10, 50          # 한 번에 지울 수 있는 상한: 기존 줄의 10%와 50줄 중 큰 값


class Store(Protocol):
    def fetch(self, sql: str, args: tuple = ()) -> list[dict]: ...
    def begin(self) -> None: ...
    def execute(self, sql: str, args: tuple = ()) -> int: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class MySqlStore:
    """공용 DB (app.core.db). 읽기는 읽기 전용 거래, 쓰기는 연결 하나에 거래 하나."""

    def __init__(self):
        self._con = self._cur = None

    def fetch(self, sql, args=()):
        from app.core import db
        return db.read_only(sql, args)

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
    fn: str
    rows: list[dict] = field(default_factory=list)       # 정리된 행(DB 칸 이름) + _status + _before(기존 줄)
    stale: list[dict] = field(default_factory=list)      # DB에는 있는데 이번 파일엔 아예 없는 기존 줄 (전체 칸 포함)
    n_existing: int = 0                                  # 같은 검사 기능의 기존 줄 수

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r["_status"]] = out.get(r["_status"], 0) + 1
        return out

    def writable(self) -> list[dict]:
        return [r for r in self.rows if r["_status"] in OKS]


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == "")


def _clean(v: Any) -> str | None:
    return None if _blank(v) else str(v).strip()


def _int(v: Any, default: int | None) -> int | None:
    if _blank(v):
        return default
    return int(float(str(v).strip()))


def _when(v: Any) -> str:
    s = _clean(v)
    if not s:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return datetime.fromisoformat(s.replace("Z", "")).strftime("%Y-%m-%d %H:%M:%S")


def read_issue_file(path: str | Path) -> list[dict]:
    """공통 15칸 CSV를 data_issue 칸 이름으로 바꾼다. 키 칸은 빈 글자·0으로. 칸이 모자라면 바로 멈춘다."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [h for h in MAP if h not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{Path(path).name}에 필요한 칸이 없습니다: {missing}")
        raw = list(reader)
    out = []
    for r in raw:
        d = {db: _clean(r.get(h)) for h, db in MAP.items()}
        try:
            for c in TEXT_KEY:
                d[c] = d[c] or ""
            d["source_row_no"] = _int(r.get("원본 행 번호"), 0)
            d["upload_id"] = _int(r.get("upload_id"), None)
            d["found_at"] = _when(r.get("찾은 시각"))
            d["_bad"] = None
        except (ValueError, TypeError):
            d["_bad"] = BAD_ROW
        out.append(d)
    return out


def _ukey(d: dict) -> tuple:
    return tuple(d[c] for c in KEY_COLS)


def build_plan(fn: str, path: str | Path, store: Store, exclude: Iterable[tuple[str, str]] = ()) -> Plan:
    """exclude: (표 이름, 검사 이름의 앞부분) 목록 — 맞는 줄은 넣지 않고 '제외(요청)'으로 센다."""
    exclude = list(exclude)
    if fn not in MINE:
        raise ValueError(f"{fn}은 이 도구로 넣지 않습니다 (A-06·A-08만). A-05는 진이님이 넣습니다.")
    plan = Plan(fn)
    seen: set = set()
    file_keys: set = set()                       # 상태와 상관없이 이번 파일에 나온 줄의 키 (정리 대상을 가릴 때 쓴다)
    for d in read_issue_file(path):
        st = d.pop("_bad") or None
        if st is None:
            file_keys.add(_ukey(d))
        if st is None and d["check_fn"] != fn:
            st = BAD_FN
        elif st is None and not (d["error_code"] or "").startswith(fn.replace("-", "") + "_"):
            st = BAD_CODE
        elif st is None and not d["check_name"]:
            st = BAD_ROW
        elif st is None and any(d["table_name"] == t and (d["check_name"] or "").startswith(pre) for t, pre in exclude):
            st = EXCLUDED
        elif st is None and any(d.get(c) is not None and len(str(d[c])) > n for c, n in LIMITS.items()):
            st = TOO_LONG
        if st is None:
            k = _ukey(d)
            st = DUP_KEY if k in seen else OK_PENDING
            seen.add(k)
        d["_status"], d["_before"], d["job_run_id"] = st, None, None
        plan.rows.append(d)

    ups = sorted({r["upload_id"] for r in plan.rows if r["_status"] == OK_PENDING and r["upload_id"] is not None})
    have: set = set()
    for i in range(0, len(ups), 500):
        part = ups[i:i + 500]
        have |= {x["upload_id"] for x in store.fetch(
            f"SELECT upload_id FROM data_upload WHERE upload_id IN ({', '.join(['%s'] * len(part))})", tuple(part))}
    existing = {tuple(x[c] for c in KEY_COLS): x for x in store.fetch(
        "SELECT issue_id, " + ", ".join(KEY_COLS) + ", check_name, value_text, reason, group_id, upload_id, found_at, job_run_id, "
        "review_status, resolution FROM data_issue WHERE check_fn = %s", (fn,))}
    for r in plan.rows:
        if r["_status"] != OK_PENDING:
            continue
        if r["upload_id"] is not None and r["upload_id"] not in have:
            r["_status"] = NO_UPLOAD
            continue
        b = existing.get(_ukey(r))
        if b is None:
            r["_status"] = NEW
        else:
            r["_before"] = b
            same = all((b.get(c) or None) == (r.get(c) or None) for c in ("value_text", "reason", "group_id"))
            r["_status"] = SAME if same else CHANGED
    plan.n_existing = len(existing)
    plan.stale = [b for k, b in existing.items() if k not in file_keys]
    return plan


def prunable(plan: Plan) -> list[dict]:
    """정리할 수 있는 줄: 이번 파일에 없고 운영자 칸(확인·처리)이 비어 있는 기존 줄."""
    return [b for b in plan.stale if not (b.get("review_status") or b.get("resolution"))]


def kept_stale(plan: Plan) -> list[dict]:
    """이번 파일에 없지만 운영자가 확인·처리를 적어서 남기는 줄."""
    return [b for b in plan.stale if (b.get("review_status") or b.get("resolution"))]


def prune_limit(n_existing: int, prune_max: int | None = None) -> int:
    return prune_max if prune_max is not None else max(PRUNE_MIN, math.ceil(n_existing * PRUNE_RATE))


def check_prune(plan: Plan, prune_max: int | None = None) -> None:
    """한꺼번에 너무 많이 지우려 하면(파일이 잘못됐을 수 있다) 멈춘다."""
    n, lim = len(prunable(plan)), prune_limit(plan.n_existing, prune_max)
    if n > lim:
        raise ValueError(f"지우려는 줄이 {n:,}줄로 상한({lim:,}줄: 기존 {plan.n_existing:,}줄의 {int(PRUNE_RATE * 100)}%)을 넘습니다. "
                         "파일이 맞는지(일부 표만 든 파일은 아닌지) 확인하고, 맞으면 --prune-max로 상한을 올리세요.")



def format_plan(plan: Plan, sample: int = 3, prune: bool = False) -> str:
    s = plan.summary()
    lines = [f"[{plan.fn}] data_issue  파일 {len(plan.rows):,}줄"]
    for st in (*OKS, EXCLUDED, BAD_FN, BAD_CODE, TOO_LONG, DUP_KEY, NO_UPLOAD, BAD_ROW):
        if s.get(st):
            lines.append(f"  {st:<14} {s[st]:>7,}")
    by: dict[str, int] = {}
    for r in plan.writable():
        by[r["error_code"]] = by.get(r["error_code"], 0) + 1
    for code, n in sorted(by.items(), key=lambda x: -x[1])[:12]:
        lines.append(f"    · {code:<26} {n:>7,}")
    for r in plan.writable()[:sample]:
        lines.append(f"  예) {r['error_code']} {r['table_name']} {r['row_key']} {r['field_name']} = {str(r['value_text'])[:30]}")
    kept = sum(1 for r in plan.writable() if r["_before"] and (r["_before"].get("review_status") or r["_before"].get("resolution")))
    if kept:
        lines.append(f"  운영자 칸(확인·처리)이 있는 {kept:,}줄은 그 칸을 그대로 둡니다")
    if plan.stale:
        pr, kp = prunable(plan), kept_stale(plan)
        lines.append(f"  이번 검사에 안 나온 기존 줄 {len(plan.stale):,}줄 (운영자 칸이 빈 {len(pr):,}줄 · 운영자 칸이 있는 {len(kp):,}줄)")
        by_stale: dict[str, int] = {}
        for b in pr:
            k = f"{b['error_code']} / {b['table_name']}"
            by_stale[k] = by_stale.get(k, 0) + 1
        for k, n in sorted(by_stale.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"    · {k:<44} {n:>6,}")
        if prune:
            lines.append(f"  --prune-stale: 운영자 칸이 빈 {len(pr):,}줄을 지웁니다 (운영자 칸이 있는 {len(kp):,}줄은 남김) — 상한 {prune_limit(plan.n_existing):,}줄")
        else:
            lines.append("  지우지 않습니다(해결됐을 수 있음, 운영자가 정함). 정리하려면 --prune-stale를 붙이세요")
    return "\n".join(lines)


def write_plan_csv(plan: Plan, out_dir: Path, stamp: str) -> Path:
    p = out_dir / f"issue_plan_{plan.fn}_{stamp}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["상태", *KEY_COLS])
        for r in plan.rows:
            w.writerow([r["_status"], *[r.get(c) for c in KEY_COLS]])
    return p


def write_stale_csv(plan: Plan, out_dir: Path, stamp: str, prune: bool = False) -> Path:
    """이번 검사에 안 나온 기존 줄 목록 (무엇이 지워질지/남을지 눈으로 확인하는 용도)."""
    p = out_dir / f"issue_stale_{plan.fn}_{stamp}.csv"
    pr = {id(b) for b in prunable(plan)}
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["처리", *KEY_COLS, "value_text", "found_at", "review_status", "resolution"])
        for b in plan.stale:
            what = ("지움(--prune-stale)" if prune else "남김(지우지 않음)") if id(b) in pr else "남김(운영자 칸 있음)"
            w.writerow([what, *[b.get(c) for c in KEY_COLS], b.get("value_text"), b.get("found_at"), b.get("review_status"), b.get("resolution")])
    return p


def write_backup(plan: Plan, out_dir: Path, stamp: str, prune: bool = False) -> Path:
    """새로 넣을 줄은 키만(되돌릴 때 지움), 이미 있는 줄은 지금 값(되돌릴 때 복원), 지울 줄은 전체 칸(되돌릴 때 되살림)을 저장한다."""
    p = out_dir / f"backup_issue_{plan.fn}_{stamp}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["종류", *KEY_COLS, "old_value_text", "old_reason", "old_group_id", "old_found_at", "old_job_run_id",
                    "old_issue_id", "old_check_name", "old_upload_id"])
        blank = lambda v: "" if v is None else v
        for r in plan.writable():
            b = r["_before"]
            if b is None:
                w.writerow(["insert", *[r.get(c) for c in KEY_COLS]])
            else:
                w.writerow(["update", *[r.get(c) for c in KEY_COLS], *[blank(b.get(c)) for c in
                                                                        ("value_text", "reason", "group_id", "found_at", "job_run_id")]])
        if prune:
            for b in prunable(plan):
                w.writerow(["delete", *[b.get(c) for c in KEY_COLS], *[blank(b.get(c)) for c in
                                                                         ("value_text", "reason", "group_id", "found_at", "job_run_id",
                                                                          "issue_id", "check_name", "upload_id")]])
    return p


_WHERE = " AND ".join(f"`{c}` = %s" for c in KEY_COLS)
INS_COLS = ["check_fn", "error_code", "check_name", "table_name", "row_key", "field_name", "value_text", "reason", "group_id",
            "source_file", "source_row_no", "upload_id", "job_run_id", "found_at", "review_status", "resolution"]


def apply_plan(plan: Plan, store: Store, job_run_id: int | None = None, prune: bool = False,
               prune_max: int | None = None) -> tuple[int, int, int]:
    """(새로 넣은 줄, 고친 줄, 지운 줄). 한 줄이라도 안 맞으면 전부 되돌리고 오류를 낸다.
    prune=True일 때만 prunable(이번 파일에 없고 운영자 칸이 빈 기존 줄)을 같은 거래 안에서 지운다."""
    if prune:
        check_prune(plan, prune_max)
    ins = f"INSERT INTO data_issue ({', '.join('`' + c + '`' for c in INS_COLS)}) VALUES ({', '.join(['%s'] * len(INS_COLS))})"
    upd = f"UPDATE data_issue SET `value_text` = %s, `reason` = %s, `group_id` = %s, `found_at` = %s, `job_run_id` = %s WHERE {_WHERE}"
    n_new = n_upd = n_del = 0
    store.begin()
    try:
        for r in plan.writable():
            r["job_run_id"] = job_run_id
            if r["_before"] is None:
                if store.execute(ins, tuple(r.get(c) for c in INS_COLS)) != 1:
                    raise RuntimeError(f"{r['error_code']} {r['row_key']}: 넣지 못했습니다. 아무것도 반영하지 않았습니다.")
                n_new += 1
            else:
                if store.execute(upd, (r["value_text"], r["reason"], r["group_id"], r["found_at"], job_run_id,
                                       *[r[c] for c in KEY_COLS])) > 1:
                    raise RuntimeError(f"{r['error_code']} {r['row_key']}: 여러 줄이 바뀌려 해서 멈춥니다. 아무것도 반영하지 않았습니다.")
                n_upd += 1
        if prune:
            dele = f"DELETE FROM data_issue WHERE {_WHERE} AND review_status IS NULL AND resolution IS NULL"
            for b in prunable(plan):
                if store.execute(dele, tuple(b[c] for c in KEY_COLS)) != 1:
                    raise RuntimeError(f"{b['error_code']} {b['row_key']}: 지우지 못했습니다(그새 운영자가 칸을 적었을 수 있어요). 아무것도 반영하지 않았습니다.")
                n_del += 1
        store.commit()
    except Exception:
        store.rollback()
        raise
    finally:
        store.close()
    return n_new, n_upd, n_del


def count_fn(store: Store, fn: str) -> int:
    """지금 DB에 있는 같은 검사 기능의 줄 수 (기존 줄 + 새로 넣은 줄 − 지운 줄과 같아야 한다)."""
    return int(store.fetch("SELECT COUNT(*) AS n FROM data_issue WHERE check_fn = %s", (fn,))[0]["n"])


def verify(plan: Plan, store: Store) -> int:
    """파일의 줄 중 지금 DB에 있는 줄 수 (넣은 줄 + 고친 줄과 같아야 한다)."""
    got = {tuple(x[c] for c in KEY_COLS) for x in store.fetch(
        "SELECT " + ", ".join(f"`{c}`" for c in KEY_COLS) + " FROM data_issue WHERE check_fn = %s", (plan.fn,))}
    return sum(1 for r in plan.writable() if _ukey(r) in got)


RESTORE_COLS = ["issue_id", *INS_COLS]


def rollback_from_backup(fn: str, backup: str | Path, store: Store, apply: bool) -> tuple[int, int, int, int]:
    """(지울 줄, 옛 값으로 되돌릴 줄, 되살릴 줄, 건너뛴 줄).
    새로 넣었던 줄은 운영자 칸이 비어 있을 때만 지우고, 고쳤던 줄은 옛 값(찾은 시각·값·사유·묶음 ID·실행 번호)으로 되돌리고,
    --prune-stale로 지웠던 줄은 원래 번호(issue_id) 그대로 되살린다(그 번호가 이미 쓰이면 새 번호). 그 뒤에 운영자가 건드린 줄은 건드리지 않는다."""
    with open(backup, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    dels, ups, back, skip = [], [], [], 0
    for r in rows:
        key = (r["check_fn"], r["error_code"], r["table_name"], r["row_key"], r["field_name"], r["source_file"], int(r["source_row_no"]))
        if key[0] != fn:
            raise ValueError(f"백업의 검사 기능({key[0]})이 {fn}과 다릅니다.")
        cur = store.fetch(f"SELECT review_status, resolution FROM data_issue WHERE {_WHERE}", key)
        if r["종류"] == "delete":
            if cur:
                skip += 1                       # 같은 줄이 이미 다시 생겼다(검사를 다시 돌렸다)
            else:
                back.append((key, r))
        elif not cur:
            skip += 1
        elif r["종류"] == "insert":
            if cur[0]["review_status"] or cur[0]["resolution"]:
                skip += 1                       # 그 뒤에 운영자가 확인·처리를 적은 줄은 지우지 않는다
            else:
                dels.append(key)
        else:
            ups.append((key, r))
    if not apply:
        return len(dels), len(ups), len(back), skip
    store.begin()
    try:
        for key in dels:
            if store.execute(f"DELETE FROM data_issue WHERE {_WHERE} AND review_status IS NULL AND resolution IS NULL", key) != 1:
                raise RuntimeError("되돌리는 중 한 줄이 안 지워져 멈춥니다. 아무것도 되돌리지 않았습니다.")
        for key, r in ups:
            old = [(r[c] if r[c] != "" else None) for c in ("old_value_text", "old_reason", "old_group_id", "old_found_at", "old_job_run_id")]
            store.execute(f"UPDATE data_issue SET `value_text` = %s, `reason` = %s, `group_id` = %s, `found_at` = %s, `job_run_id` = %s WHERE {_WHERE}",
                          (*old, *key))
        for key, r in back:
            g = lambda c: (r.get(c) if r.get(c) not in (None, "") else None)
            vals = {"issue_id": _int(g("old_issue_id"), None), "check_fn": key[0], "error_code": key[1], "check_name": g("old_check_name") or key[1],
                    "table_name": key[2], "row_key": key[3], "field_name": key[4], "value_text": g("old_value_text"), "reason": g("old_reason"),
                    "group_id": g("old_group_id"), "source_file": key[5], "source_row_no": key[6], "upload_id": _int(g("old_upload_id"), None),
                    "job_run_id": _int(g("old_job_run_id"), None), "found_at": g("old_found_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "review_status": None, "resolution": None}
            iid = vals["issue_id"]
            taken = bool(iid) and bool(store.fetch("SELECT 1 AS x FROM data_issue WHERE issue_id = %s", (iid,)))
            cols = RESTORE_COLS if iid and not taken else INS_COLS
            sql = f"INSERT INTO data_issue ({', '.join('`' + c + '`' for c in cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
            if store.execute(sql, tuple(vals[c] for c in cols)) != 1:
                raise RuntimeError(f"{key[1]} {key[3]}: 되살리지 못했습니다. 아무것도 되돌리지 않았습니다.")
        store.commit()
    except Exception:
        store.rollback()
        raise
    finally:
        store.close()
    return len(dels), len(ups), len(back), skip


def stamp_now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
