"""8장 신규 · 기존 · 갱신과 80 변경 기록.

- 신규: INSERT (upload_id = 이번 업로드). db_first/last 일시는 넣지 않음 (DB가 채움).
- 기존: 비교 칸이 모두 같으면 바꾸지 않음.
- 갱신: 다른 칸만 UPDATE + db_last_updated_at 갱신 + 칸마다 80 한 줄.
- 원본_위치 · 자료_기간은 최신 값으로 바꾸되 80에 남기지 않음.
- 업로드ID와 첫 적재 일시는 바꾸지 않음.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Sequence

from app.services.load.ai01_port import AI_COLS
from app.services.load.store import RECURRENCE_COLS

# 비교 칸: 명세서 5장 2·4–26·28–30번 (원본에서 오는 값)
TRACKED = [
    "source_receipt_no", "source_type", "receipt_channel", "inflow_media", "report_type_raw", "received_date",
    "processed_date", "has_processed_date", "processing_days", "request_org", "transfer_org", "location_text", "gu",
    "admin_dong_name", "lat", "lon", "gid", "coord_method", "coord_accuracy", "photo_cnt", "first_photo_at",
    "occurred_at", "reported_at", "display_tag", "raw_pii_patterns", "dup_flag", "repeated_title",
]
SILENT = ("raw_position", "data_period")
# 주소 변환(AI-03)으로 얻은 값이 같이 움직이는 칸. 위치_원문이 바뀐 때만 다시 계산한다 (7장 ②, 8장).
COORD_GROUP = ("gu", "admin_dong_name", "lat", "lon", "gid", "coord_method", "coord_accuracy")
NEVER_CLEAR = ("dup_flag", "repeated_title")      # 올린 파일 안에서만 세므로 값이 없다고 지우지 않음 (명세서 11장 미결 1)
DATE_COLS = {"received_date", "processed_date"}
DT_COLS = {"first_photo_at", "occurred_at", "reported_at"}
FLOAT_COLS = {"lat", "lon", "class_confidence"}


def norm_value(col: str, v: Any) -> Any:
    if v is None or v == "":
        return None
    if col in DATE_COLS:
        return v.isoformat() if isinstance(v, date) and not isinstance(v, datetime) else str(v)[:10]
    if col in DT_COLS:
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        s = str(v)
        return s + " 00:00:00" if len(s) == 10 else s + ":00" if len(s) == 16 else s
    if col in FLOAT_COLS:
        return round(float(v), 9)
    if col in ("photo_cnt", "processing_days"):
        return int(v)
    return str(v)


def as_text(v: Any) -> str | None:
    return None if v is None else str(v)


@dataclass
class Counts:
    new: int = 0
    existing: int = 0
    updated: int = 0
    change_rows: int = 0
    missing: int = 0


def _derived_coords(old: dict) -> bool:
    """본문 좌표가 아니라 주소·장소 표현으로 채워진 좌표인가 (AI-03이 채운 값)."""
    m = old.get("coord_method")
    return bool(m) and m != "없음" and not str(m).startswith("원본 좌표")


def diff_record(new: dict, old: dict) -> tuple[dict, dict]:
    """(바뀐 칸 {칸: (이전, 새)}, 조용히 바꿀 칸 {칸: 새}) 를 돌려준다.

    - 이번 파일에 본문 좌표가 없고 위치_원문도 같으면, 이미 채워진 좌표 칸은 건드리지 않는다.
    - AI-01 칸은 새 값이 있을 때만 본다 (모델이 실패하거나 AI-01을 다시 안 불렀다고 지우지 않음).
      빈 칸을 처음 채우는 것은 80에 남기지 않는다 (AI-01 문의 2번, 첫 실행 때 80이 수십만 줄 늘지 않게).
    """
    cols = list(TRACKED)
    if new.get("coord_method") is None and _derived_coords(old) \
            and norm_value("location_text", new.get("location_text")) == norm_value("location_text", old.get("location_text")):
        cols = [c for c in cols if c not in COORD_GROUP]
    changes, silent = {}, {}
    for c in cols:
        a, b = norm_value(c, old.get(c)), norm_value(c, new.get(c))
        if c in NEVER_CLEAR and b is None:
            continue
        if a != b:
            changes[c] = (old.get(c), new.get(c))
    human = old.get("class_method") == "사람"           # 사람이 고친 관련 여부는 덮어쓰지 않는다 (C-08)
    ai_like = list(AI_COLS) + (["class_method"] if "class_method" in new else [])
    derived = ai_like + (list(RECURRENCE_COLS) if "recurrence_flag" in new else [])
    for c in derived:                                 # AI-01 · 재발 표시: 처음 채우는 것은 80에 남기지 않고, 값이 바뀔 때만 남긴다
        a, b = norm_value(c, old.get(c)), norm_value(c, new.get(c))
        if a == b or (b is None and c in ai_like) or (human and c in ai_like):
            continue
        if a is None:
            silent[c] = new[c]
        else:
            changes[c] = (old.get(c), new.get(c))
    silent.update({c: new[c] for c in SILENT if new.get(c) != old.get(c)})
    return changes, silent


def apply_records(store, records: Sequence[dict], existing: dict[str, dict], upload_id: int, file_name: str,
                  data_period: str) -> Counts:
    counts = Counts()
    fresh: list[dict] = []
    pending: list[tuple[str, dict, bool]] = []          # 새 민원을 넣은 뒤에 반영할 갱신 (재발 표시가 새 민원을 가리킬 수 있음)
    change_rows: list[dict] = []
    batch = f"{upload_id} {file_name}"
    for rec in records:
        rec["data_period"] = data_period
        old = existing.get(rec["complaint_id"])
        if old is None:
            rec["upload_id"] = upload_id
            fresh.append(rec)
            continue
        changes, silent = diff_record(rec, old)
        if not changes and not silent:
            counts.existing += 1
            continue
        if changes:
            counts.updated += 1
            for col, (o, n) in changes.items():
                label = ("AI-01 " if col in AI_COLS or col == "class_method" else "") + batch
                change_rows.append(dict(complaint_id=rec["complaint_id"], changed_column=col, old_value=as_text(o),
                                        new_value=as_text(n), load_batch=label[:60], changed_by_type="적재", changed_by_user=None))
        else:
            counts.existing += 1
        pending.append((rec["complaint_id"], {**{c: n for c, (_o, n) in changes.items()}, **silent}, bool(changes)))
    if fresh:
        store.insert_complaints(fresh)
    for cid, values, touch in pending:
        store.update_complaint(cid, values, touch=touch)
    counts.new = len(fresh)
    if change_rows:
        store.insert_changes(change_rows)
    counts.change_rows = len(change_rows)
    return counts
