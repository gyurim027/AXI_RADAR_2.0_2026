"""법령·업무 기준 관리 DB 읽기·쓰기 (SQL v2.1: 87 jurisdiction · 88 jurisdiction_dept · 89 standard_change · 62 setting_version)."""
from __future__ import annotations

from app.core import db


class StandardsRepository:
    # ── 87·88 담당 부서 표 ──────────────────────────
    def jurisdiction(self) -> list[dict]:
        """문제 유형 한 줄 + 1차 해결 부서 목록. F-05 make_drafts가 쓰는 모양(dept = 부서를 ' / '로 이은 글자)도 같이."""
        rows = db.read_only(
            "SELECT jurisdiction_id, problem, mvp_scope, related_dept, basis, confirm_status, note, setting_version_id, "
            "updated_at FROM jurisdiction ORDER BY jurisdiction_id")
        depts = db.read_only(
            "SELECT jurisdiction_id, sort_no, gu_name, condition_text, dept_name, org_level FROM jurisdiction_dept "
            "ORDER BY jurisdiction_id, sort_no, jurisdiction_dept_id")
        by: dict[str, list[dict]] = {}
        for d in depts:
            by.setdefault(d["jurisdiction_id"], []).append(d)
        out = []
        for r in rows:
            ds = by.get(r["jurisdiction_id"], [])
            label = " / ".join(
                ((f"{d['condition_text']}: " if d.get("condition_text") else (f"{d['gu_name']}: " if d.get("gu_name") else ""))
                 + (d.get("dept_name") or "근거 없음")) for d in ds)
            out.append({"id": r["jurisdiction_id"], "problem": r["problem"], "dept": label or None,
                        "related": r.get("related_dept"), "status": r.get("confirm_status"), "basis": r.get("basis"),
                        "mvp": r.get("mvp_scope"), "note": r.get("note"), "setting_version_id": r.get("setting_version_id"),
                        "depts": ds})
        return out

    # ── 89 규정 변경 기록 ───────────────────────────
    def save_changes(self, changes: list[dict], job_run_id: int | None) -> int:
        if not changes:
            return 0
        with db.connect() as con:
            with con.cursor() as cur:
                for c in changes:
                    cur.execute(
                        "INSERT INTO standard_change (change_kind, doc_name, where_text, change_type, before_text, after_text, "
                        "effective_date, related_jur, related_criteria, job_run_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (c["kind"], (c.get("name") or "")[:200], (c.get("where") or "")[:200] or None, c["change"],
                         _cut(c.get("before")), _cut(c.get("after")), c.get("date") or None,
                         ",".join(c.get("related_jur") or []) or None,
                         ",".join(x["criterion_id"] for x in c.get("criteria") or [] if x.get("criterion_id"))[:200] or None,
                         job_run_id))
            con.commit()
        return len(changes)

    def list_changes(self, unseen_only: bool, limit: int) -> list[dict]:
        sql = ("SELECT standard_change_id, change_kind, doc_name, where_text, change_type, before_text, after_text, "
               "effective_date, related_jur, related_criteria, job_run_id, detected_at, seen_at FROM standard_change")
        if unseen_only:
            sql += " WHERE seen_at IS NULL"
        sql += " ORDER BY detected_at DESC, standard_change_id DESC LIMIT %s"
        return db.read_only(sql, (limit,))

    def mark_seen(self, change_id: int, user_id: int) -> bool:
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("SELECT 1 FROM standard_change WHERE standard_change_id = %s", (change_id,))
                if not cur.fetchone():
                    return False
                cur.execute("UPDATE standard_change SET seen_at = NOW(), seen_by = %s "
                            "WHERE standard_change_id = %s AND seen_at IS NULL", (user_id, change_id))
            con.commit()
        return True

    # ── 62 수정안 제안 (승인은 I-07, 진규) ───────────
    def submit_proposal(self, label: str, content: str, proposed_by: int) -> int:
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO setting_version (setting_kind, version_label, content_ref, proposed_by, proposed_at, "
                    "approval_status) VALUES ('담당 부서 표', %s, %s, %s, NOW(), '제안')", (label[:255], content[:255], proposed_by))
                new_id = cur.lastrowid
            con.commit()
        return int(new_id)


def _cut(s, n: int = 500):
    if s is None:
        return None
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


_repo = StandardsRepository()


def set_repository(r: StandardsRepository) -> None:
    global _repo
    _repo = r


def get_repository() -> StandardsRepository:
    return _repo
