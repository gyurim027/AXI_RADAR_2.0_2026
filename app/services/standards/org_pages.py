"""A-12 업무분장 — 성남시청 누리집 '조직도 > 부서' 페이지(PDF로 저장한 것) 읽기 (초안 v0.1).

페이지 모양: 부서 이름 → (팀마다) '○○팀장 / 전화번호 / ○○팀 업무 총괄' → '주무관 / 전화번호 / 담당업무' 반복.
- 사람 이름은 없고 직위·업무 전화번호만 있다. 전화번호는 버리고 '부서 · 팀 · 담당업무'만 남긴다.
- 구청 페이지는 본문의 '수정구·중원구·분당구' 글자로, 없으면 대표 전화 국번(729-5 수정 · 729-6 중원 · 729-7 분당)으로 구를 정한다.
  국번 규칙은 이번(2026-10-23) 저장본 9개에서 확인한 것이라, 바뀌면 고친다.
결과는 duty_table.Duty 목록이라 compare()에 그대로 넣는다 (dept = '분당구 건설과 건설행정팀'처럼 구·과·팀).
"""
from __future__ import annotations

import re

from app.services.standards.duty_table import Duty

PHONE = re.compile(r"^\d{2,3}-\d{3,4}-\d{4}$")
TEAM_HEAD = re.compile(r"^(.+?(팀|TF팀|센터|단))장$")
TEAM_TOTAL = re.compile(r"^(.+?(팀|센터|단))\s*업무\s*총괄$")
DEPT_TOTAL = re.compile(r"^(?:(수정구|중원구|분당구)\s*)?(.+?(과|관|소|센터))\s*업무\s*총괄$")
SKIP = {"홈", "성남소개", "총괄 조직도", "조직도", "총괄조직도", "부서별 팩스번호", "직위", "전화번호", "담당업무", "주무관",
        "조직정보가 없습니다."}
GU_BY_PHONE = {"5": "수정구", "6": "중원구", "7": "분당구"}


def _team(name: str) -> str:
    """'*단속요청은 … ★주차관리팀' · '중원구 도로조명팀' → 팀 이름만"""
    m = re.findall(r"[가-힣A-Za-z]+(?:팀|센터|단)", name)
    return m[-1] if m else name.strip()


def _gu(lines: list[str]) -> str | None:
    """과장 대표 번호의 국번으로 시·구를 가린다. 구청이면 본문에 구 이름이 있으면 그것을 쓴다."""
    for i, l in enumerate(lines):
        if l.endswith("과장") and i + 1 < len(lines) and PHONE.match(lines[i + 1]):
            digit = lines[i + 1].split("-")[2][0]
            if digit in GU_BY_PHONE:
                named = next((g for g in ("수정구", "중원구", "분당구") for x in lines if g in x), None)
                return named or GU_BY_PHONE[digit]
            return None
    return None


def parse_org_page(text: str) -> list[Duty]:
    lines = [" ".join(l.split()) for l in (text or "").splitlines()]
    lines = [l for l in lines if l]
    dept = next((l for l in lines if l not in SKIP and re.match(r"^[가-힣]{2,10}(과|관|소|센터)$", l)), None)
    if not dept:
        return []
    gu = _gu(lines)
    prefix = f"{gu} {dept}" if gu else f"시 {dept}"
    team_names = {m.group(1) for l in lines for m in [TEAM_TOTAL.match(l) or TEAM_HEAD.match(l)] if m}

    out: list[Duty] = []
    team = None
    buf: list[str] = []
    after_phone = False

    def add(s: str):
        s = s.strip(" ,")
        if s and team:
            out.append(Duty(f"{prefix} {team}", s))

    def flush():
        nonlocal buf
        cur = ""
        for part in buf:
            if part.startswith("○"):
                add(cur)
                cur = part.lstrip("○").strip()
            elif cur and len(cur.split("\n")[-1]) >= 30 and not cur.endswith((",", ".", ")")):
                cur += part                      # PDF가 줄을 중간에서 끊은 곳은 붙여 씀
            else:
                cur = f"{cur} {part}".strip()
        add(cur)
        buf = []

    for l in lines:
        if l in SKIP:
            if l in ("주무관", "직위"):
                flush()
                after_phone = False
            continue
        m = TEAM_TOTAL.match(l)
        if m:
            flush(); team = _team(m.group(1)); after_phone = False
            continue
        h = TEAM_HEAD.match(l)
        if h:                                    # 팀장 줄로 팀을 먼저 정하고, '○○팀 업무 총괄'이 오면 그걸로 바꿈
            flush(); team = _team(h.group(1)); after_phone = False
            continue
        if DEPT_TOTAL.match(l) or l in team_names or l == dept or l.endswith("과장"):
            flush(); after_phone = False
            continue
        if PHONE.match(l):
            flush(); after_phone = True
            continue
        if after_phone:
            buf.append(l)
    flush()
    seen, uniq = set(), []
    for d in out:                                # 주무관 여러 명이 같은 업무를 맡으면 한 줄만
        if (d.dept, d.duty) not in seen:
            seen.add((d.dept, d.duty)); uniq.append(d)
    return uniq


def parse_org_folder(folder) -> list[Duty]:
    """한 번에 저장한 부서 페이지 묶음(폴더) → 사무 목록. PDF·TXT. 총괄 조직도처럼 팀이 없는 페이지는 0줄."""
    from pathlib import Path
    from app.services.ai05.extract import READERS
    out: list[Duty] = []
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() == ".txt":
            out += parse_org_page(p.read_text(encoding="utf-8"))
        elif p.suffix.lower() == ".pdf":
            out += parse_org_page(READERS[".pdf"](p))
    return out
