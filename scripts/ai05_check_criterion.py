"""W04-19 유형별 조문 표 원문 대조 — 법령 색인(data/ai05/criterion.json)의 조문이 AI-05가 가진 법령 원문(색인)에 있는지 하나씩 확인한다.

실행 (저장소 루트)
    uv run python -m scripts.ai05_check_criterion                 # 결과를 화면에 요약, 자세한 표는 docs/ai05/criterion_check.csv
    uv run python -m scripts.ai05_check_criterion --only-type     # 문제 유형(T 코드)에 쓰는 줄만

확인 상태 (한 줄에 하나)
    확인됨        조항 칸의 조문이 모두 원문 색인에 있음
    일부 없음      일부 조문이 원문 색인에 없음 (없는 조문을 '없는 조문' 칸에 적음)
    원문 없음      그 법령 원문 자체가 색인에 없음 → 국가법령정보센터에서 원문을 받아 색인에 더해야 함
    조문 표기 없음  조항 칸이 '법 전체'·장·절·별표처럼 '제N조'가 아니라 자동 대조를 못 함 → 사람이 확인
    대조 대상 아님  종류가 '공식문서'(자료 출처·공고·통지서 등)라 법령 원문과 대조하지 않음

법을 해석하지 않는다. 조문 번호가 원문에 있는지만 본다. 내용이 맞는지는 사람이 원문을 읽고 정한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from app.services.ai05.rag import LawIndex, arts_in, norm_law

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ai05"
OUT = ROOT / "docs" / "ai05" / "criterion_check.csv"
TYPE = re.compile(r"(?<![A-Za-z0-9])T\d{2}[a-z]?(?![0-9])")
COLS = ["criterion_id", "종류", "법령", "조항", "T 코드", "확인 상태", "없는 조문", "색인 법령 이름", "기존 확인 수준", "메모"]


def law_names(row: dict, prev: list[str]) -> list[str]:
    """'자전거 이용 활성화에 관한 법률 (자전거법, …)' → ['자전거 이용 활성화에 관한 법률']
    괄호·[별표]·<개정> 꼬리를 떼고, ' / '로 여러 법령이 적혀 있으면 나눈다. '같은 규칙 (…)'이면 바로 앞 줄 이름."""
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]|<[^>]*>", "", row.get("이름") or "").strip()
    if name.startswith("같은"):
        return prev
    name = re.split(r"\s{2,}", name)[0]                          # '…시행규칙  자전거도로대장'처럼 [별지] 뒤에 남은 제목은 뗌
    return [n.strip(" ·ㆍ") for n in name.split("/") if n.strip(" ·ㆍ")]


def check(rows: list[dict], ix: LawIndex) -> list[dict]:
    out, prev = [], []
    names = {}
    for c in ix.C:
        names.setdefault(norm_law(c["law_name"]), c["law_name"])
    annex_host = {}
    for c in ix.C:
        for t in (c.get("annex_title"), c.get("section") if c.get("annex") else None):
            if t:
                annex_host.setdefault(norm_law(re.sub(r"\([^)]*\)", "", t)), c["law_name"])
    for r in rows:
        memo_extra = []
        laws = law_names(r, prev)
        if laws and not (r.get("이름") or "").startswith("같은"):
            prev = laws
        arts = arts_in(r.get("조항·만든 곳"))
        have = [l for l in laws if norm_law(l) in ix.by_law]
        lack = [l for l in laws if norm_law(l) not in ix.by_law]
        for l in list(lack):                                     # 별첨·별지로 다른 법령 안에 들어 있는 문서 (예: 보도계획 및 설치지침 → 도시·군관리계획수립지침 [별첨 4])
            host = annex_host.get(norm_law(l))
            if host:
                lack.remove(l); have.append(host)
                memo_extra.append(f"{l}은 {host} 안의 별첨·별지로 색인에 있음")
        memo = "; ".join(memo_extra + (["색인에 없는 법령: " + ", ".join(lack)] if have and lack else []))
        if r.get("종류") != "법령" and not have:
            state, missing = "대조 대상 아님", []              # 공식문서(자료 출처·공고·통지서 등) — 법령 원문이 아님
        elif not laws or not have:
            state, missing = "원문 없음", arts
        elif not arts:
            state, missing = "조문 표기 없음", []              # 법 전체·장·절·별표·서식 → 사람이 확인
        else:
            law = have[0]
            missing = [a for a in arts if not any(ix.article(l, a, include_future=True) for l in have)]
            # '제66조의10 (시행령 제73조의8)'처럼 시행령·시행규칙 조문을 같이 적은 경우: 그 법의 시행령·시행규칙에서 찾음
            sub = {a: f"{l} {k}" for a in missing for l in have for k in ("시행령", "시행규칙")
                   if ix.article(f"{l} {k}", a, include_future=True)}
            if sub:
                missing = [a for a in missing if a not in sub]
                memo = "; ".join(x for x in [memo] + [f"{a}는 {v}에 있음" for a, v in sub.items()] if x)
            state = "확인됨" if not missing else "일부 없음"
        out.append({"criterion_id": r.get("criterion_id"), "종류": r.get("종류"), "법령": " / ".join(laws),
                    "조항": r.get("조항·만든 곳") or "", "T 코드": " ".join(dict.fromkeys(TYPE.findall(str(r.get("RADAR에서 쓴 곳") or "")))),
                    "확인 상태": state, "없는 조문": " ".join(missing),
                    "색인 법령 이름": " / ".join(names[norm_law(l)] for l in have), "기존 확인 수준": r.get("확인 수준") or "",
                    "메모": memo})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W04-19 법령 색인 원문 대조")
    ap.add_argument("--only-type", action="store_true", help="T 코드에 쓰는 줄만")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    rows = json.loads((DATA / "criterion.json").read_text(encoding="utf-8"))
    res = check(rows, LawIndex.load(DATA / "law_index.pkl"))
    if args.only_type:
        res = [r for r in res if r["T 코드"]]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(res)
    from collections import Counter
    cnt = Counter(r["확인 상태"] for r in res)
    print(f"법령 색인 {len(res)}줄: " + " · ".join(f"{k} {v}" for k, v in cnt.most_common()))
    for r in res:
        if r["T 코드"] and r["확인 상태"] in ("원문 없음", "일부 없음"):
            print(f"  ! {r['T 코드']:<12} {r['criterion_id']:<5} {r['확인 상태']}: {r['법령']} {r['없는 조문']}")
    print("자세한 표:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
