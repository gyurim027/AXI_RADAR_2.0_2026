"""F-05 담당 부서 표 수정안 만들기 (초안 v0.1). AI 후보 + 사람 승인.

A-12가 찾은 사무 변화(부서 옮김 · 새 사무 · 없어진 사무)를 담당 부서 표의 문제 유형과 맞춰, 표를 고칠 '안'을 만든다.
안은 확정이 아니다. RADAR 운영자가 고쳐서 62 setting_version에 '제안'으로 올리고, 시 도로과가 승인한다(I-07, 진규).

담당 부서 표 한 줄 (어드민 목업 JURISDICTION 모양, DB 표는 아직 없음 — 표가 생기면 저장소만 바꿈)
    {"id": "JUR-05", "problem": "불법 주정차", "dept": "각 구 경제교통과 주차관리팀", "related": "관할 경찰서",
     "status": "확인됨", "basis": "도로교통법 제32조"}
수정안 한 줄 (어드민 목업 DEPT_DRAFTS 모양)
    {"id", "jur_id", "problem", "from", "to", "basis", "article", "change", "needs_review", "evidence"}

사무위임 조례 [별표](구청장에게 위임하는 사무)를 비교한 경우
- 새 사무 = 시에서 구로 넘어감 → to = "각 구 (구청장 위임, 담당 팀 확인 필요)"
- 없어진 사무 = 구에서 시로 돌아옴 → to = 그 사무의 시 소관 부서
일반 업무분장 문서(부서 옮김)는 to = 새 부서.
"""
from __future__ import annotations

import re
from typing import Iterable

# 문제 유형 글자 → 사무 글자에서 찾을 말 (담당 부서 표의 problem이 이 말을 담고 있으면 아래 말로 사무를 찾음)
SYNONYMS = {
    "주정차": ("주ㆍ정차", "주·정차", "주정차", "주차"),
    "적치": ("적치", "노점", "노상적치물"),
    "조도": ("가로등", "보안등", "조명"),
    "가로등": ("가로등", "보안등"),
    "보도": ("보도", "도로유지관리", "도로 유지"),
    "점자블록": ("보도", "도로유지관리"),
    "파손": ("도로유지관리", "보수", "유지관리"),
    "단차": ("도로유지관리", "보수"),
    "신호": ("신호", "교통안전시설"),
    "횡단보도": ("횡단보도", "교통안전시설"),
    "점용": ("점용",),
    "보호구역": ("보호구역",),
    "자전거": ("자전거",),
}
DELEGATED_TO = "각 구 (구청장 위임, 담당 팀 확인 필요)"


def _words(problem: str) -> list[str]:
    out = []
    for key, words in SYNONYMS.items():
        if key in (problem or "").replace(" ", ""):
            out += words
    return list(dict.fromkeys(out))


def _short(text: str, n: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def make_drafts(changes: Iterable[dict], jurisdiction: Iterable[dict], doc_name: str,
                delegation_annex: bool = True) -> list[dict]:
    """A-12 changes × 담당 부서 표 → 수정안 목록. 같은 표 줄에 여러 변화가 걸리면 각각 한 안."""
    drafts = []
    rows = list(jurisdiction)
    for ch in changes:
        if ch.get("change") not in ("부서 옮김", "새 사무", "없어진 사무"):
            continue
        duty = ch.get("duty") or ""
        for row in rows:
            words = _words(row.get("problem", ""))
            hit = next((w for w in words if w in duty), None)
            if not hit:
                continue
            if ch["change"] == "부서 옮김":
                to = ch.get("to_dept")
            elif ch["change"] == "새 사무":
                to = DELEGATED_TO if delegation_annex else ch.get("to_dept")
            else:
                to = ch.get("from_dept") if delegation_annex else "확인 필요 (사무가 없어짐)"
            if not to or to == row.get("dept"):
                continue
            drafts.append({
                "id": f"dd-{len(drafts) + 1}", "jur_id": row.get("id"), "problem": row.get("problem"),
                "from": row.get("dept"), "to": to, "basis": doc_name,
                "article": _short(f"{doc_name} ({duty}: {ch['change']})", 200), "change": ch["change"],
                "needs_review": True,             # 사람이 원문을 보고 고친 뒤 올린다
                "evidence": {"matched_word": hit, "duty": _short(duty), "basis_law": _short(ch.get("basis") or "", 80),
                             "before": _short(ch.get("before") or ""), "after": _short(ch.get("after") or "")},
            })
    return drafts


def proposal_text(draft: dict) -> str:
    """62 setting_version.content_ref(255자)에 넣는 한 줄."""
    s = f"{draft.get('jur_id')} {draft.get('problem')}: {draft.get('from')} → {draft.get('to')} (근거 {draft.get('basis')})"
    return s if len(s) <= 255 else s[:254] + "…"


class ProposalStore:
    """62 setting_version에 '제안' 한 줄. 승인·돌려보내기는 I-07(진규)이 한다."""

    def submit(self, draft: dict, proposed_by: int, label: str | None = None) -> int:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(setting_version_id), 0) + 1 AS n FROM setting_version FOR UPDATE")
                new_id = int(cur.fetchone()["n"])
                cur.execute(
                    "INSERT INTO setting_version (setting_version_id, setting_kind, version_label, content_ref, "
                    "proposed_by, proposed_at, approval_status) VALUES (%s, '담당 부서 표', %s, %s, %s, NOW(), '제안')",
                    (new_id, label or f"담당 부서 표 수정안 {draft.get('jur_id')}", proposal_text(draft), proposed_by))
            con.commit()
        return new_id


def check_draft(draft: dict) -> None:
    """올리기 전 확인: 필수 칸이 비었거나 사람이 아직 손대지 않았으면 막는다."""
    for k in ("jur_id", "problem", "from", "to", "basis"):
        if not draft.get(k):
            raise ValueError(f"수정안에 {k}가 비어 있습니다")
    if "확인 필요" in str(draft.get("to")):
        raise ValueError("받는 부서(to)를 확인해 정확한 팀 이름으로 고친 뒤 올려 주세요")
    if re.search(r"[<>]", str(draft)):
        raise ValueError("수정안에 쓸 수 없는 글자가 있습니다")
