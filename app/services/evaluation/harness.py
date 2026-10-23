"""공통 평가 틀 (W05-06, 초안 v0.1). 정답 목록을 넣으면 AI 기능마다 같은 방식으로 점수를 낸다.

정답 목록 (CSV UTF-8 또는 xlsx 첫 시트, 한 줄에 한 문제) — 단톡방 요청 형식과 같다
    case_id | 입력 | 기대 답 | 맞음 기준 | 메모
    01      | T18  | 도로교통법 제32조 | 3등 안 | 주정차 단속
- 기대 답이 여러 개면 ' | ' 또는 ';'로 나눈다.
- 맞음 기준: 같음 · 포함 · 안 들어감 · N등 안(예: 5등 안) · 못 찾음
- 민원 원문·개인정보는 넣지 않는다 (ISS-032). 가린 문장이나 만든 문장만.

어댑터 = 각 기능이 만드는 함수 하나: run(입력 글자) -> 결과
    결과는 글자 하나, 글자 목록(순위 순서), 또는 None / [] (= 못 찾음)
    예: app/services/ai05/eval_adapter.py 의 run

판정
    같음      결과(글자)가 기대 답 중 하나와 같음. 목록이면 1등이 같음
    포함      기대 답이 모두 결과 안에 있음 (목록이면 이어 붙인 글자에서 찾음)
    안 들어감  결과가 있고, 기대 답이 하나도 결과 안에 없음 (빈 결과·오류는 통과 아님)
    N등 안    기대 답 중 하나가 목록 앞 N개 중 하나에 들어 있음
    못 찾음    결과가 None 또는 빈 값
비교 전에 띄어쓰기를 하나로 줄이고 영문은 소문자로 바꾼다.
"""
from __future__ import annotations

import csv
import importlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

COLS = {"case_id": ("case_id", "번호", "id"), "input": ("입력", "input"), "expected": ("기대 답", "기대답", "expected"),
        "rule": ("맞음 기준", "맞음기준", "rule"), "note": ("메모", "note")}
RULES = ("같음", "포함", "안 들어감", "못 찾음")
TOP_N = re.compile(r"^\s*(\d+)\s*등\s*안\s*$")


@dataclass
class Case:
    case_id: str
    input: str
    expected: list[str]
    rule: str
    note: str = ""


@dataclass
class CaseResult:
    case_id: str
    rule: str
    ok: bool
    got: Any = None
    reason: str = ""


@dataclass
class Report:
    name: str
    total: int
    passed: int
    by_rule: dict = field(default_factory=dict)
    failed: list = field(default_factory=list)
    errors: int = 0
    at: str = ""

    @property
    def rate(self) -> float:
        return round(self.passed / self.total * 100, 1) if self.total else 0.0


def norm(s: Any) -> str:
    return " ".join(str(s).split()).lower()


def _split(expected: str) -> list[str]:
    parts = re.split(r"\s*\|\s*|\s*;\s*", expected or "")
    return [p for p in (x.strip() for x in parts) if p]


def check_rule(rule: str) -> str:
    rule = " ".join((rule or "").split())
    if rule in RULES or TOP_N.match(rule):
        return rule
    raise ValueError(f"맞음 기준을 알 수 없습니다: '{rule}' (같음 · 포함 · 안 들어감 · N등 안 · 못 찾음)")


# ── 정답 목록 읽기 ───────────────────────────────────

def _rows_from_file(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise RuntimeError("xlsx를 읽으려면 openpyxl이 필요합니다. 엑셀에서 'CSV UTF-8'로 저장해 주세요.") from None
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h or "").strip() for h in rows[0]]
        return [dict(zip(head, ["" if v is None else str(v) for v in r])) for r in rows[1:] if any(r)]
    raise ValueError("정답 목록은 .csv 또는 .xlsx만 읽습니다")


def load_cases(path: str | Path) -> list[Case]:
    rows = _rows_from_file(Path(path))
    if not rows:
        return []
    keys = {}
    for want, names in COLS.items():
        keys[want] = next((k for k in rows[0] if k and k.strip() in names), None)
    missing = [w for w in ("input", "rule") if not keys[w]]
    if missing:
        raise ValueError(f"칸이 없습니다: {missing} — 칸 이름은 case_id · 입력 · 기대 답 · 맞음 기준 · 메모")
    cases = []
    for i, r in enumerate(rows, 1):
        get = lambda w: (r.get(keys[w]) or "").strip() if keys[w] else ""
        if not get("input") and not get("rule"):
            continue
        cases.append(Case(case_id=get("case_id") or f"{i:02d}", input=get("input"), expected=_split(get("expected")),
                          rule=check_rule(get("rule")), note=get("note")))
    return cases


# ── 판정 ────────────────────────────────────────────

def judge(case: Case, got: Any) -> tuple[bool, str]:
    items = got if isinstance(got, (list, tuple)) else ([] if got in (None, "") else [got])
    items = [norm(x) for x in items if x not in (None, "")]
    blob = " ".join(items)
    exp = [norm(e) for e in case.expected]
    rule = case.rule
    if rule == "못 찾음":
        return (not items), ("" if not items else "결과가 나왔음")
    if not exp:
        return False, "기대 답이 비어 있음"
    if rule == "같음":
        return (bool(items) and items[0] in exp), "1등이 기대 답과 다름"
    if rule == "포함":
        miss = [e for e in exp if e not in blob]
        return (not miss), ("없음: " + ", ".join(miss) if miss else "")
    if rule == "안 들어감":
        if not items:                                  # 빈 결과는 '안 들어감'을 통과한 게 아니다
            return False, "결과 없음"
        hit = [e for e in exp if e in blob]
        return (not hit), ("들어감: " + ", ".join(hit) if hit else "")
    n = int(TOP_N.match(rule).group(1))
    ok = any(e in it for it in items[:n] for e in exp)
    return ok, ("" if ok else f"앞 {n}개 안에 없음")


def load_adapter(spec: str) -> Callable[[str], Any]:
    """'app.services.ai05.eval_adapter:run' 꼴."""
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn or "run")


def evaluate(name: str, cases: list[Case], adapter: Callable[[str], Any]) -> Report:
    rep = Report(name=name, total=len(cases), passed=0, at=datetime.now().isoformat(timespec="seconds"))
    for c in cases:
        key = "N등 안" if TOP_N.match(c.rule) else c.rule
        b = rep.by_rule.setdefault(key, {"total": 0, "passed": 0})
        b["total"] += 1
        try:
            got = adapter(c.input)
            ok, why = judge(c, got)
        except Exception as exc:                 # 한 문제가 오류여도 나머지는 계속
            got, ok, why = None, False, f"오류({type(exc).__name__})"
            rep.errors += 1
        if ok:
            rep.passed += 1
            b["passed"] += 1
        else:
            shown = got[:5] if isinstance(got, (list, tuple)) else got
            rep.failed.append(asdict(CaseResult(c.case_id, c.rule, ok, shown, why)))
    return rep


def summary_text(rep: Report) -> str:
    lines = [f"[{rep.name}] {rep.passed}/{rep.total} 맞음 ({rep.rate}%)" + (f" · 오류 {rep.errors}" if rep.errors else "")]
    for rule, b in rep.by_rule.items():
        lines.append(f"  - {rule}: {b['passed']}/{b['total']}")
    for f in rep.failed:
        lines.append(f"  ✗ {f['case_id']} ({f['rule']}) {f['reason']}")
    return "\n".join(lines)


def save_report(rep: Report, out_dir: str | Path = "out/eval") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{rep.name}_{datetime.now():%y%m%d_%H%M}.json"
    path.write_text(json.dumps({**asdict(rep), "rate": rep.rate}, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    return path
