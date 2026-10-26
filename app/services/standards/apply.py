"""F-05 마지막 단계: 승인된 담당 부서 표 수정안(62)을 87 jurisdiction · 88 jurisdiction_dept에 반영한다.

부르는 곳: I-07 승인 처리 (진규). 62 줄을 '승인'으로 바꾸고 커밋한 **뒤에** 부른다.
    from app.services.standards.apply import apply_approved, preview, ApplyError
    preview(sv_id)                       # 바꾸기 전에 화면에 보여 줄 것 (DB 안 바꿈)
    apply_approved(sv_id, user_id)       # 실제 반영 (한 거래로: 88 줄 바꿈 + 87.setting_version_id)

지키는 것
- 62 줄이 setting_kind='담당 부서 표' · approval_status='승인'일 때만 반영한다.
- 같은 수정안을 두 번 반영하지 않는다 (87.setting_version_id가 이미 이 번호면 '이미 반영됨').
- 제안한 뒤 표가 바뀌었으면(지금 표 ≠ 수정안의 '전') 반영하지 않는다 → 다시 제안.
- '확인 필요'가 남은 수정안(예: "각 구(확인 필요)")은 반영하지 않는다 → 부서를 정해서 다시 제안.
- 그대로 남는 부서 줄은 원래 값(구·조건·시/구)을 그대로 둔다. 새로 생긴 줄만 글자에서 읽는다.
- 반영 기록: 62(전 → 후 글자, 승인한 사람·시각) + 87.setting_version_id. 89(규정 변경)에는 쓰지 않는다 (A-11·A-12가 찾은 변경용).
- 승인됐는데 반영이 안 된 줄은 unapplied()로 찾아 다시 부르면 된다.
  (같은 유형에 더 나중 수정안이 반영되면 앞 수정안도 목록에 보인다. 다시 부르면 table_changed로 막힌다)

수정안 글자 (62.content_ref, dept_draft.proposal_text)
    "JUR-05 가로등·보안등 문제: <전> → <후> (근거 <문서>)"
    <전>·<후>는 담당 부서 표 화면과 같은 꼴: "부서" 또는 "조건: 부서" 또는 "구: 부서"를 " / "로 이음
"""
from __future__ import annotations

import re

from app.core import db

GU_LIST = ("수정구", "중원구", "분당구")
KIND = "담당 부서 표"
JUR_ID = re.compile(r"^(JUR-\d+)\s")


class ApplyError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ── 글자 ↔ 88 줄 ──────────────────────────────────

def dept_label(d: dict) -> str:
    """88 한 줄 → 화면 글자 (repository.jurisdiction()과 같은 규칙)."""
    head = f"{d['condition_text']}: " if d.get("condition_text") else (f"{d['gu_name']}: " if d.get("gu_name") else "")
    return head + (d.get("dept_name") or "근거 없음")


def table_label(depts: list[dict]) -> str:
    return " / ".join(dept_label(d) for d in depts)


def parse_piece(piece: str) -> dict:
    """새로 생긴 글자 한 조각 → 88 줄 값. '구: 부서'면 구, 그 밖의 '조건: 부서'면 조건(+조건 안에 구 이름이 있으면 구)."""
    piece = piece.strip()
    head, sep, dept = piece.partition(": ")
    if not sep:
        head, dept = "", piece
    dept = dept.strip()
    gu = head if head in GU_LIST else next((g for g in GU_LIST if g in head), None)
    return {"gu_name": gu, "condition_text": None if (not head or head in GU_LIST) else head[:100],
            "dept_name": None if dept in ("", "근거 없음") else dept[:200], "org_level": "구" if gu else None}


def parse_proposal(content: str, problem: str) -> tuple[str, str, str]:
    """62.content_ref → (jur_id, 전, 후)."""
    if not content or content.endswith("…"):
        raise ApplyError(422, "content_cut", "수정안 글자가 255자에서 잘려 반영할 수 없습니다. 짧게 다시 제안해 주세요")
    m = JUR_ID.match(content)
    if not m:
        raise ApplyError(422, "content_format", "수정안 글자에서 담당 부서 표 ID(JUR-…)를 찾지 못했습니다")
    jur_id = m.group(1)
    head = f"{jur_id} {problem}: "
    if not content.startswith(head):
        raise ApplyError(422, "content_format", "수정안의 문제 유형이 지금 담당 부서 표와 다릅니다")
    body = content[len(head):]
    cut = body.rfind(" (근거 ")
    if cut < 0 or " → " not in body[:cut]:
        raise ApplyError(422, "content_format", "수정안 글자 꼴이 '전 → 후 (근거 …)'가 아닙니다")
    before, after = body[:cut].split(" → ", 1)
    if not after.strip():
        raise ApplyError(422, "content_format", "반영할 담당 부서가 비어 있습니다")
    return jur_id, before.strip(), after.strip()


def plan(depts: list[dict], after: str) -> list[dict]:
    """반영 뒤 88 줄 목록. 글자가 그대로인 줄은 원래 값을 쓴다."""
    old = {}
    for d in depts:
        old.setdefault(dept_label(d), d)
    rows = []
    for i, piece in enumerate([p for p in after.split(" / ") if p.strip()], 1):
        src = old.get(piece.strip())
        base = ({k: src.get(k) for k in ("gu_name", "condition_text", "dept_name", "org_level")} if src
                else parse_piece(piece))
        rows.append({**base, "sort_no": i, "kept": bool(src)})
    return rows


# ── DB ──────────────────────────────────────────

def _load(cur, sv_id: int, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    cur.execute("SELECT setting_version_id, setting_kind, content_ref, approval_status, approved_by, approved_at "
                "FROM setting_version WHERE setting_version_id = %s" + suffix, (sv_id,))
    sv = cur.fetchone()
    if not sv:
        raise ApplyError(404, "proposal_not_found", "수정안(62)을 찾을 수 없습니다")
    if sv["setting_kind"] != KIND:
        raise ApplyError(400, "not_jurisdiction", "담당 부서 표 수정안이 아닙니다")
    m = JUR_ID.match(sv["content_ref"] or "")
    if not m:
        raise ApplyError(422, "content_format", "수정안 글자에서 담당 부서 표 ID(JUR-…)를 찾지 못했습니다")
    cur.execute("SELECT jurisdiction_id, problem, setting_version_id FROM jurisdiction WHERE jurisdiction_id = %s" + suffix,
                (m.group(1),))
    jur = cur.fetchone()
    if not jur:
        raise ApplyError(404, "jurisdiction_not_found", f"담당 부서 표에 {m.group(1)}이 없습니다")
    cur.execute("SELECT jurisdiction_dept_id, sort_no, gu_name, condition_text, dept_name, org_level "
                "FROM jurisdiction_dept WHERE jurisdiction_id = %s ORDER BY sort_no, jurisdiction_dept_id" + suffix,
                (jur["jurisdiction_id"],))
    depts = list(cur.fetchall())
    jur_id, before, after = parse_proposal(sv["content_ref"], jur["problem"])
    return sv, jur, depts, before, after


def _check(sv, jur, depts, before, after, need_approved: bool) -> str | None:
    """반영할 수 없는 이유 (없으면 None). 이미 반영된 경우는 'already'."""
    if need_approved and sv["approval_status"] != "승인":
        raise ApplyError(409, "not_approved", f"승인된 수정안만 반영합니다 (지금 상태: {sv['approval_status']})")
    if jur.get("setting_version_id") == sv["setting_version_id"]:
        return "already"
    if table_label(depts) != before:
        raise ApplyError(409, "table_changed", "제안한 뒤 담당 부서 표가 바뀌었습니다. 지금 표를 보고 다시 제안해 주세요")
    if "확인 필요" in after:
        raise ApplyError(422, "needs_review", "'확인 필요'가 남은 수정안은 반영하지 않습니다. 부서를 정해서 다시 제안해 주세요")
    if after == before:
        raise ApplyError(422, "no_change", "전과 후가 같습니다")
    return None


def preview(sv_id: int) -> dict:
    """반영하면 어떻게 바뀌는지 (DB 안 바꿈). 승인 전에도 볼 수 있다."""
    with db.connect() as con:
        try:
            with con.cursor() as cur:
                cur.execute("START TRANSACTION READ ONLY")
                sv, jur, depts, before, after = _load(cur, sv_id)
                state = _check(sv, jur, depts, before, after, need_approved=False)
                return {"setting_version_id": sv_id, "jur_id": jur["jurisdiction_id"], "problem": jur["problem"],
                        "status": sv["approval_status"], "already_applied": state == "already",
                        "before": before, "after": after, "rows": plan(depts, after)}
        finally:
            con.rollback()


def apply_approved(sv_id: int, applied_by: int | None = None) -> dict:
    """승인된 수정안 반영. 한 거래로 88 줄 바꿈 + 87.setting_version_id. 실패하면 아무것도 안 바뀐다."""
    with db.connect() as con:
        with con.cursor() as cur:
            # 잠금을 얻은 뒤 현재 값을 읽는다. 대기 전에 읽은 RR 스냅샷으로 판정하면
            # 서로 다른 제안이 같은 부서표를 연이어 덮어쓸 수 있다.
            sv, jur, depts, before, after = _load(cur, sv_id, lock=True)
            if _check(sv, jur, depts, before, after, need_approved=True) == "already":
                return {"ok": True, "already_applied": True, "jur_id": jur["jurisdiction_id"], "setting_version_id": sv_id}
            rows = plan(depts, after)
            cur.execute("DELETE FROM jurisdiction_dept WHERE jurisdiction_id = %s", (jur["jurisdiction_id"],))
            for r in rows:
                cur.execute("INSERT INTO jurisdiction_dept (jurisdiction_id, sort_no, gu_name, condition_text, dept_name, "
                            "org_level) VALUES (%s, %s, %s, %s, %s, %s)",
                            (jur["jurisdiction_id"], r["sort_no"], r["gu_name"], r["condition_text"], r["dept_name"],
                             r["org_level"]))
            cur.execute("UPDATE jurisdiction SET setting_version_id = %s WHERE jurisdiction_id = %s",
                        (sv_id, jur["jurisdiction_id"]))
        con.commit()
    return {"ok": True, "already_applied": False, "jur_id": jur["jurisdiction_id"], "setting_version_id": sv_id,
            "applied_by": applied_by, "before": before, "after": after, "rows": rows}


def unapplied() -> list[dict]:
    """승인됐는데 아직 87·88에 반영되지 않은 담당 부서 표 수정안 (다시 부를 것)."""
    return db.read_only(
        "SELECT s.setting_version_id, s.content_ref, s.approved_at FROM setting_version s "
        "WHERE s.setting_kind = %s AND s.approval_status = '승인' "
        "AND NOT EXISTS (SELECT 1 FROM jurisdiction j WHERE j.setting_version_id = s.setting_version_id) "
        "ORDER BY s.approved_at, s.setting_version_id", (KIND,))
