"""A-11 법령 개정 확인 (초안 v0.1).

지금 색인을 만든 조문 조각(data/ai05/chunks.jsonl)과, 새로 받은 원문으로 만든 조각을 조문 단위로 비교한다.
- 법령: 새로 들어옴 · 빠짐 · 시행일 바뀜
- 조문: 바뀜 · 새 조문 · 없어짐 (같은 법령·별표·조·항·구역을 같은 조문으로 본다)
- 바뀐 법령이 57 criterion(법령 색인)의 어느 행과 이어지는지(radar_usage 문제 유형 코드)도 붙인다 → 대응표 확인 대상
결과 한 줄 = 어드민 '규정 변경' 목업 모양 {kind, name, where, date, before, after, change, criteria}
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

SNIPPET = 300


def _norm_law(name: str | None) -> str:
    """AI-05와 같은 법령 이름 키 (괄호·공백·가운뎃점 차이 무시, 보행안전법 같은 줄임말 풀기)"""
    from app.services.ai05.rag import norm_law
    return norm_law(name)


def _key(c: dict) -> tuple:
    return (_norm_law(c.get("law_name")), c.get("annex") or "", c.get("article") or "", bool(c.get("addenda")),
            c.get("para") or "", c.get("section") or "")


def _where(c: dict) -> str:
    parts = []
    if c.get("annex"):
        parts.append(f"[{c['annex']}]")
    if c.get("article"):
        parts.append(("부칙 " if c.get("addenda") else "") + c["article"] + (f"({c['article_title']})" if c.get("article_title") else "")
                     + (f" {c['para']}" if c.get("para") else ""))
    elif c.get("section"):
        parts.append(f"'{c['section']}'")
    return " ".join(parts) or "전체"


def _text(c: dict) -> str:
    return " ".join((c.get("text") or "").split())


def _digest(c: dict) -> str:
    return hashlib.sha1(_text(c).encode("utf-8")).hexdigest()


def _cut(s: str) -> str:
    return s if len(s) <= SNIPPET else s[: SNIPPET - 1] + "…"


def read_chunks(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def criteria_by_law(criteria: Iterable[dict]) -> dict[str, list[dict]]:
    """57 criterion 행을 법령 이름으로 묶는다. 칸: criterion_id · name · article_or_publisher · radar_usage"""
    out: dict[str, list[dict]] = {}
    for r in criteria:
        name = r.get("name") or r.get("이름") or ""
        out.setdefault(_norm_law(name), []).append(
            {"criterion_id": r.get("criterion_id"), "article": r.get("article_or_publisher") or r.get("조항·만든 곳"),
             "usage": r.get("radar_usage") or r.get("RADAR에서 쓴 곳")})
    return out


def _direct(rows: list[dict], article: str | None) -> list[dict]:
    """조문이 바뀐 경우, 그 조를 직접 적어 둔 criterion 행만 (예: 제32조 → L17 '제32조~제35조'). 조가 없으면 법령 전체 행."""
    if not article:
        return rows
    from app.services.ai05.rag import arts_in
    return [r for r in rows if article in arts_in(r.get("article") or "")]


def compare(old: list[dict], new: list[dict], criteria: Iterable[dict] = ()) -> dict:
    crit = criteria_by_law(criteria)
    old_by = {}
    for c in old:
        old_by.setdefault(_key(c), c)
    new_by = {}
    for c in new:
        new_by.setdefault(_key(c), c)

    def laws(chunks):
        d = {}
        for c in chunks:
            d.setdefault(_norm_law(c.get("law_name")), {"name": c.get("law_name"), "effective": set()})
            if c.get("effective"):
                d[_norm_law(c.get("law_name"))]["effective"].add(c["effective"])
        return d

    ol, nl = laws(old), laws(new)
    law_rows = []
    for k in sorted(set(ol) | set(nl)):
        o, n = ol.get(k), nl.get(k)
        if o and not n:
            status = "빠짐"
        elif n and not o:
            status = "새로 들어옴"
        elif o["effective"] != n["effective"]:
            status = "시행일 바뀜"
        else:
            status = None
        law_rows.append({"name": (n or o)["name"], "status": status,
                         "old_effective": max(o["effective"]) if o and o["effective"] else None,
                         "new_effective": max(n["effective"]) if n and n["effective"] else None,
                         "criteria": crit.get(k, [])})

    changes = []
    for k in sorted(set(old_by) | set(new_by)):
        o, n = old_by.get(k), new_by.get(k)
        if o and n and _digest(o) == _digest(n):
            continue
        if o and not n and k[0] in nl:
            change = "없어짐"
        elif n and not o and k[0] in ol:
            change = "새 조문"
        elif o and n:
            change = "바뀜"
        else:
            continue                                  # 법령째 들어오거나 빠진 것은 법령 줄에서 본다
        c = n or o
        changes.append({"kind": "법령", "name": c.get("law_name"), "where": _where(c), "change": change,
                        "date": (n or {}).get("effective"), "status": (n or o).get("status"),
                        "before": _cut(_text(o)) if o else None, "after": _cut(_text(n)) if n else None,
                        "criteria": _direct(crit.get(k[0], []), c.get("article"))})

    touched = [r for r in law_rows if r["status"]]
    changed_laws = {c["name"] for c in changes}
    for r in law_rows:
        if not r["status"] and r["name"] in changed_laws:
            r["status"] = "조문 바뀜"
            touched.append(r)
    return {"laws": touched, "changes": changes,
            "summary": {"laws_checked": len(law_rows), "laws_changed": len(touched), "articles_changed": len(changes),
                        "criteria_to_check": sorted({x["criterion_id"] for c in changes for x in c["criteria"] if x["criterion_id"]}),
                        "criteria_same_law": sorted({x["criterion_id"] for r in touched for x in r["criteria"] if x["criterion_id"]})}}


LAW_STATUS_TO_CHANGE = {"시행일 바뀜": "시행일 바뀜", "새로 들어옴": "새 조문", "빠짐": "없어짐"}


def rows_to_save(rep: dict) -> list[dict]:
    """89 standard_change에 넣을 줄: 조문 변경 + 조문 변경 없이 법령째 바뀐 것(시행일 바뀜·새로 들어옴·빠짐)."""
    out = list(rep["changes"])
    with_articles = {c["name"] for c in rep["changes"]}
    for law in rep["laws"]:
        if law["status"] in LAW_STATUS_TO_CHANGE and law["name"] not in with_articles:
            out.append({"kind": "법령", "name": law["name"], "where": "법령 전체", "change": LAW_STATUS_TO_CHANGE[law["status"]],
                        "date": law.get("new_effective"), "before": law.get("old_effective"), "after": law.get("new_effective"),
                        "criteria": law.get("criteria", [])})
    return out
