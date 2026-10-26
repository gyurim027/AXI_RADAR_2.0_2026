"""F-05 담당 부서 표 수정안 만들기 (v0.2, 10/26 AI 추출 추가). AI 후보 + 사람 승인.

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
    "노점": ("노점", "적치", "가두판매점"),
    "공사": ("점용", "굴착"),
    "육교": ("육교", "지하차도", "교량"),
    "지하보도": ("지하보도", "지하차도"),
    "교통안전시설": ("교통안전시설", "노면", "표지"),
}
DELEGATED_TO = "각 구 (구청장 위임, 담당 팀 확인 필요)"


GENERIC = {"보도", "도로", "도로유지관리", "도로 유지", "유지관리", "보수"}   # 여러 유형에 다 걸리는 말은 약하게


def _core(problem: str) -> str:
    """'불법주정차 (보도·횡단보도 금지구역)' → '불법주정차' (괄호 안 설명은 비교에서 뺌)"""
    return re.sub(r"\([^)]*\)", "", problem or "").replace(" ", "")


def _words(problem: str) -> list[str]:
    out = []
    for key, words in SYNONYMS.items():
        if key in _core(problem):
            out += words
    return list(dict.fromkeys(out))


def score(problem: str, duty: str) -> float:
    """문제 유형과 사무 글자가 얼마나 겹치나. 구체적인 말 1점, 흔한 말(보도·도로·유지관리) 0.5점, 같은 말은 한 번만."""
    return sum(0.5 if w in GENERIC else 1.0 for w in _words(problem) if w in (duty or ""))


def best_rows(rows: list[dict], duty: str) -> list[dict]:
    """점수가 가장 높은 유형만 (1점 이상). 흔한 말만 겹친 유형은 고르지 않는다."""
    scored = [(score(r.get("problem", ""), duty), r) for r in rows]
    top = max((sc for sc, _ in scored), default=0)
    return [r for sc, r in scored if sc >= 1 and sc == top]


def _short(text: str, n: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _road_condition(row: dict, road: str | None) -> str | None:
    """AI가 뽑은 도로 종류가 담당 부서 표 줄의 '나뉘는 조건'(88 condition_text)에 나오면 그 조건 글자."""
    if not road:
        return None
    for d in row.get("depts") or []:
        cond = d.get("condition_text") or ""
        if road in cond:
            return cond
    return None


def make_drafts(changes: Iterable[dict], jurisdiction: Iterable[dict], doc_name: str,
                delegation_annex: bool = True, use_ai: bool = True, extractor=None) -> list[dict]:
    """A-12 changes × 담당 부서 표 → 수정안 목록. 같은 표 줄에 여러 변화가 걸리면 각각 한 안.

    use_ai=True면 바뀐 문장을 공통 LLM(f05_extract)으로 읽어 (업무, 부서, 도로 종류)를 뽑고, 그 업무 글자로 표 줄을 찾는다.
    AI를 쓸 수 없으면(작업 미등록·Ollama 꺼짐) 그 변화는 규칙 방식(사무 글자 × 낱말 점수)으로 만든다.
    수정안마다 method = 'AI' / '규칙'을 붙여 승인하는 사람이 알 수 있게 한다."""
    if extractor is None and use_ai:
        from app.services.standards.extract_llm import extract as extractor
    drafts = []
    rows = list(jurisdiction)
    for ch in changes:
        if ch.get("change") not in ("부서 옮김", "새 사무", "없어진 사무"):
            continue
        duty = ch.get("duty") or ""
        ai = extractor(ch.get("after") or ch.get("before") or duty) if use_ai else None
        item = (ai or {}).get("items", [None])[0] if ai and ai.get("items") else None
        method = f"AI ({ai.get('model') or 'f05_extract'})" if item else "규칙"
        key_text = f"{item['duty']} {duty}" if item else duty      # AI가 뽑은 업무 글자를 더해 표 줄을 찾음
        for row in best_rows(rows, key_text):
            hit = ", ".join(w for w in _words(row.get("problem", "")) if w in key_text)
            if ch["change"] == "부서 옮김":
                to = (item or {}).get("dept") or ch.get("to_dept")
            elif ch["change"] == "새 사무":
                to = DELEGATED_TO if delegation_annex else ((item or {}).get("dept") or ch.get("to_dept"))
            else:
                to = ch.get("from_dept") if delegation_annex else "확인 필요 (사무가 없어짐)"
            if not to or to in (row.get("dept") or ""):        # 이미 그 부서가 맡고 있으면 고칠 것 없음
                continue
            road = (item or {}).get("road_type")
            ev = {"matched_word": hit, "duty": _short(duty), "basis_law": _short(ch.get("basis") or "", 80),
                  "before": _short(ch.get("before") or ""), "after": _short(ch.get("after") or "")}
            if item:
                ev["ai"] = {"duty": item["duty"], "dept": item.get("dept"), "road_type": road,
                            "road_condition": _road_condition(row, road)}
            drafts.append({
                "id": f"dd-{len(drafts) + 1}", "jur_id": row.get("id"), "problem": row.get("problem"),
                "from": row.get("dept"), "to": to, "basis": doc_name, "road_type": road, "method": method,
                "article": _short(f"{doc_name} ({duty}: {ch['change']})", 200), "change": ch["change"],
                "needs_review": True,             # 사람이 원문을 보고 고친 뒤 올린다
                "evidence": ev,
            })
    return drafts


def proposal_text(draft: dict) -> str:
    """62 setting_version.content_ref(255자)에 넣는 한 줄."""
    s = f"{draft.get('jur_id')} {draft.get('problem')}: {draft.get('from')} → {draft.get('to')} (근거 {draft.get('basis')})"
    return s if len(s) <= 255 else s[:254] + "…"


def submit(draft: dict, proposed_by: int, label: str | None = None) -> int:
    """확인을 마친 수정안을 62 setting_version에 '제안'으로 올린다 (SQL v2.1 자동 번호). 승인·돌려보내기는 I-07(진규)."""
    from app.services.standards.repository import get_repository
    check_draft(draft)
    return get_repository().submit_proposal(label or f"담당 부서 표 수정안 {draft.get('jur_id')}", proposal_text(draft),
                                            proposed_by)


def link_jurisdiction(changes: list[dict], jurisdiction: Iterable[dict]) -> list[dict]:
    """변경마다 걸리는 담당 부서 표 ID(related_jur)를 붙인다 (89 standard_change.related_jur).
    업무분장 변경 = 사무 글자가 문제 유형의 말과 겹침 · 법령 변경 = 표의 근거 칸에 그 법령 이름이 나옴"""
    rows = list(jurisdiction)
    for ch in changes:
        hits = []
        for row in rows:
            if ch.get("kind") == "업무분장":
                continue
            elif ch.get("name") and ch["name"].replace(" ", "") in (row.get("basis") or "").replace(" ", ""):
                hits.append(row.get("id"))
        if ch.get("kind") == "업무분장":
            hits = [r.get("id") for r in best_rows(rows, ch.get("duty") or "")]
        ch["related_jur"] = sorted({h for h in hits if h})
    return changes


def check_draft(draft: dict) -> None:
    """올리기 전 확인: 필수 칸이 비었거나 사람이 아직 손대지 않았으면 막는다."""
    for k in ("jur_id", "problem", "from", "to", "basis"):
        if not draft.get(k):
            raise ValueError(f"수정안에 {k}가 비어 있습니다")
    if "확인 필요" in str(draft.get("to")):
        raise ValueError("받는 부서(to)를 확인해 정확한 팀 이름으로 고친 뒤 올려 주세요")
    if re.search(r"[<>]", str(draft)):
        raise ValueError("수정안에 쓸 수 없는 글자가 있습니다")
