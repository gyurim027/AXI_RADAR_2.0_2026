"""C-10 재발 표시: 같은 장소 · 같은 유형으로 처리된 뒤 다시 들어온 민원을 찾아 표시한다. 지우거나 처리 상태를 바꾸지 않는다.

판단 기준 (기능정의서에 숫자가 없어 제안한 기준 — 기획 확인 필요, docs/load/재발표시_DB추가_제안.md):
- 같은 장소 = 같은 격자 칸(gid), 같은 유형 = 같은 보행_유형(ped_type), 보행_유형이 아직 없으면 같은 신고유형_원문(report_type_raw).
  둘 중 하나라도 비면 판단에서 뺀다. 유형 목록(ISS-016)이 정해지면 보행_유형만 쓰도록 _kind() 한 곳만 바꾼다.
- 이전 건 = 처리일이 있고(처리일이 없는 민원은 재발 판단에서 뺀다) 그 처리일이 이번 민원 접수일보다 앞선 민원.
- recurrence_flag = '재발 N회' (N = 이전 건 수), recurrence_prev_id = 가장 최근에 처리된 이전 건.
원문은 쓰지 않는다. 이미 DB에 저장된 값과 이번 파일의 값만 쓴다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence


def _day(v) -> str | None:
    return None if v in (None, "") else str(v)[:10]


def _kind(r: dict):
    return r.get("ped_type") or r.get("report_type_raw")


def mark_recurrence(records: Sequence[dict], priors: Iterable[dict]) -> int:
    """records에 recurrence_flag · recurrence_prev_id를 채운다. 돌려주는 값: 재발로 표시한 건수."""
    batch_ids = {r["complaint_id"] for r in records}
    pool: dict[tuple, list[tuple[str, str]]] = defaultdict(list)       # (gid, 유형) → [(처리일, 민원ID)]
    for p in priors:                                                  # DB의 지난 민원 (이번 파일에 다시 들어온 것은 새 값을 쓰려고 뺌)
        if p["complaint_id"] not in batch_ids and _day(p["processed_date"]) and _kind(p):
            pool[(p["gid"], _kind(p))].append((_day(p["processed_date"]), p["complaint_id"]))
    for r in records:                                                 # 이번 파일 안의 민원도 서로 이전 건이 된다
        if r["gid"] and _kind(r) and r["processed_date"]:
            pool[(r["gid"], _kind(r))].append((_day(r["processed_date"]), r["complaint_id"]))
    marked = 0
    for r in records:
        r["recurrence_flag"] = r["recurrence_prev_id"] = None
        if not (r["gid"] and _kind(r) and r["received_date"]):
            continue
        before = [(d, i) for d, i in pool.get((r["gid"], _kind(r)), ()) if i != r["complaint_id"] and d < _day(r["received_date"])]
        if before:
            r["recurrence_flag"] = f"재발 {len(before)}회"
            r["recurrence_prev_id"] = max(before)[1]
            marked += 1
    return marked


def recompute_recurrence(store, label: str) -> tuple[int, int]:
    """DB에 저장된 값만으로 재발 표시를 처음부터 다시 계산한다 (원문 필요 없음). 돌려주는 값: (재발 건수, 바뀐 민원 수).

    쓰는 때: ① 달을 시간 순서대로 올리지 못했을 때 ② AI-03이 좌표(gid)를 채운 뒤 ③ 보행_유형이 채워진 뒤.
    이미 값이 있던 칸이 바뀐 것만 80 src_complaint_change에 남기고 db_last_updated_at을 갱신한다 (처음 채우는 것은 남기지 않음).
    label은 80 적재_회차에 들어간다.
    """
    if not store.supports_recurrence():
        raise RuntimeError("79에 재발 표시 칸이 없습니다 (SQL v2.x 필요).")
    rows = store.recurrence_rows()
    old = {r["complaint_id"]: (r.get("recurrence_flag"), r.get("recurrence_prev_id")) for r in rows}
    marked = mark_recurrence(rows, [])
    changes, touched = [], 0
    for r in rows:
        new = (r["recurrence_flag"], r["recurrence_prev_id"])
        if new == old[r["complaint_id"]]:
            continue
        touched += 1
        logged = False
        for col, o, n in (("recurrence_flag", old[r["complaint_id"]][0], new[0]), ("recurrence_prev_id", old[r["complaint_id"]][1], new[1])):
            if o is not None and o != n:                        # 처음 채우는 것은 80에 남기지 않는다 (AI-01 칸과 같은 방식)
                logged = True
                changes.append(dict(complaint_id=r["complaint_id"], changed_column=col, old_value=o, new_value=n,
                                    load_batch=label[:60], changed_by_type="적재", changed_by_user=None))
        store.update_complaint(r["complaint_id"], {"recurrence_flag": new[0], "recurrence_prev_id": new[1]}, touch=logged)
    if changes:
        store.insert_changes(changes)
    return marked, touched
