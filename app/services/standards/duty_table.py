"""A-12 업무분장 변경 확인 (초안 v0.1).

'성남시 사무위임 조례 [별표 1] 구청장에게 위임하는 사무'처럼 "소관 부서 → 사무 → 근거 법규"로 적힌 문서 두 판을 비교한다.
- parse(): 글자 → [{dept, duty, basis}] (○ 사무 아래 ㆍ·- 세부 사무는 '상위 사무 > 세부 사무'로 묶음)
- compare(): 같은 사무가 다른 부서로 옮김 · 새 사무 · 없어진 사무 · 근거 법규 바뀜 · 부서 새로 생김/없어짐
- 보행안전 관련 사무(보도·보행·횡단보도·가로등·주정차 등)에는 related=True를 붙여 먼저 보게 한다
결과 한 줄 = 어드민 '규정 변경' 목업 모양 {kind: '업무분장', name, where, before, after, change, ...}

글자는 AI-05와 같은 방법으로 hwp·hwpx·pdf에서 뽑는다(app/services/ai05/extract.py). 문서 모양이 다르면 parse 규칙을 더한다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

DEPT = re.compile(r"^[가-힣]{2,12}(과|관|담당관|팀|센터|사업소|단|실|국|소)$")
SKIP = re.compile(r"^(소\s*관|부\s*서|일련|번호|위\s*임.*명|근\s*거.*규|■.*|<.*>|구청장에게.*|\d+)$")
LAW = re.compile(r"(법|령|규칙|조례|규정|지침|고시)(\s|$|\s*제|\s*\d|,)|같은\s*법|제\d+조")
BULLET_TOP = re.compile(r"^○\s*")
BULLET_SUB = re.compile(r"^(ㆍ|·|-|－)\s*")
RELATED = ("보도", "보행", "횡단", "가로등", "보안등", "조명", "도로", "주ㆍ정차", "주정차", "주·정차", "주차", "교통약자",
           "보호구역", "점용", "적치", "신호", "육교", "지하보도", "통학로")


@dataclass
class Duty:
    dept: str
    duty: str
    basis: str = ""

    @property
    def key(self) -> str:
        return re.sub(r"[\s․·ㆍ・,()]", "", self.duty)


def _clean(s: str) -> str:
    return " ".join(s.replace("　", " ").split())


def parse(text: str) -> list[Duty]:
    """소관 부서 → ○ 사무 / ㆍ 세부 사무 → 근거 법규 순서의 글자를 행으로."""
    out: list[Duty] = []
    dept = None
    top: Duty | None = None         # 지금 ○ 사무 (세부 사무 앞에 이름을 붙임)
    cur: Duty | None = None
    for raw in (text or "").splitlines():
        indented = raw[:1] in (" ", "\t", "　")
        line = _clean(raw)
        if not line or SKIP.match(line):
            continue
        if DEPT.match(line):
            if line != dept:                              # 쪽이 넘어가며 같은 부서 이름이 다시 나오면 이어 씀
                dept, top, cur = line, None, None
            continue
        if dept is None:
            continue
        if BULLET_TOP.match(line):
            cur = top = Duty(dept, BULLET_TOP.sub("", line))
            out.append(cur)
            continue
        if BULLET_SUB.match(line):
            name = BULLET_SUB.sub("", line)
            if top is not None and not top.basis and out and out[-1] is top:
                out.pop()                                 # 세부 사무가 있는 ○ 줄은 제목이라 빼고 세부로 나눔
            cur = Duty(dept, f"{_trim_title(top.duty)} > {name}" if top else name)
            out.append(cur)
            continue
        if cur is None:
            continue
        if LAW.search(line) and not indented:
            cur.basis = f"{cur.basis}, {line}" if cur.basis else line
        else:                                             # 줄바꿈으로 이어진 사무 이름 · (6층 이하 …) 같은 조건
            cur.duty = f"{cur.duty} {line}"
    return [d for d in out if d.duty]


def _trim_title(t: str | None) -> str:
    t = re.sub(r"(에\s*관한|에\s*의한)?\s*다음의\s*권한$", "", t or "").strip()
    return re.sub(r"에\s*관한\s*권한$", "", t).strip()


def is_related(d: Duty) -> bool:
    return any(w in d.duty for w in RELATED)


def compare(old: list[Duty], new: list[Duty], name: str = "업무분장") -> dict:
    ob: dict[str, list[Duty]] = {}
    for d in old:
        ob.setdefault(d.key, []).append(d)
    nb: dict[str, list[Duty]] = {}
    for d in new:
        nb.setdefault(d.key, []).append(d)

    changes = []

    def add(change, where, before, after, d: Duty, **kw):
        changes.append({"kind": "업무분장", "name": name, "where": where, "change": change, "duty": d.duty,
                        "before": before, "after": after, "related": is_related(d), **kw})

    for k in sorted(set(ob) | set(nb)):
        o_depts = {d.dept for d in ob.get(k, [])}
        n_depts = {d.dept for d in nb.get(k, [])}
        if k not in nb:
            d = ob[k][0]
            add("없어진 사무", d.dept, f"{d.dept}: {d.duty}", None, d, from_dept=d.dept)
            continue
        if k not in ob:
            d = nb[k][0]
            add("새 사무", d.dept, None, f"{d.dept}: {d.duty}", d, to_dept=d.dept)
            continue
        if o_depts != n_depts:
            d = nb[k][0]
            frm, to = ", ".join(sorted(o_depts - n_depts)) or None, ", ".join(sorted(n_depts - o_depts)) or None
            add("부서 옮김", to or d.dept, f"{frm}: {d.duty}" if frm else None, f"{to}: {d.duty}" if to else None, d,
                from_dept=frm, to_dept=to, basis=d.basis)
            continue
        ob_basis = {(d.dept, d.basis) for d in ob[k]}
        nb_basis = {(d.dept, d.basis) for d in nb[k]}
        if ob_basis != nb_basis:
            d = nb[k][0]
            add("근거 바뀜", d.dept, ob[k][0].basis, d.basis, d)

    od, nd = {d.dept for d in old}, {d.dept for d in new}
    depts = {"new": sorted(nd - od), "gone": sorted(od - nd)}
    changes.sort(key=lambda c: (not c["related"], c["change"], c["where"]))
    return {"changes": changes, "depts": depts,
            "summary": {"old_duties": len(old), "new_duties": len(new), "changes": len(changes),
                        "related": sum(1 for c in changes if c["related"])}}


def to_rows(duties: list[Duty]) -> list[dict]:
    return [asdict(d) for d in duties]
