"""민원ID 확인: 월별 파일에서 만든 민원ID를 DB v2 79 src_complaint(SQL 덤프)의 같은 달 행과 건수로 비교한다.

원문(제목·본문)은 출력하지 않는다. 건수만 출력한다.
실행: python scripts/load_verify.py <79_src_complaint.txt> <월별 xlsx> <YYYY> <MM> [<월별 xlsx> <YYYY> <MM> ...]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.load.ids import make_ids  # noqa: E402
from app.services.load.reader import read_rows  # noqa: E402

LINE = re.compile(r"^\('(C[0-9a-f]{12})', (?:NULL|'[^']*'), '(\d{4})년 파일 · (\d\d)월 시트 · 번호 (\d+)'")


def read_dump(path: str) -> dict[tuple[int, int], dict[int, str]]:
    out: dict[tuple[int, int], dict[int, str]] = defaultdict(dict)
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            m = LINE.match(line)
            if m:
                out[(int(m[2]), int(m[3]))][int(m[4])] = m[1]
    return out


def main(argv: list[str]) -> int:
    dump = read_dump(argv[0])
    bad = 0
    for i in range(1, len(argv), 3):
        path, y, m = argv[i], int(argv[i + 1]), int(argv[i + 2])
        rows = sorted(read_rows(Path(path).read_bytes()), key=lambda r: r.number)
        ids, numbered = make_ids(rows)
        mine = {r.number: cid for r, cid in zip(rows, ids)}
        theirs = dump.get((y, m), {})
        same = sum(1 for n, c in mine.items() if theirs.get(n) == c)
        print(f"{y}-{m:02d} 파일 {len(mine)}건 · DB {len(theirs)}건 · 일치 {same}건 · 다름 {len(mine) - same}건 · 순번 붙은 행 {numbered}건")
        bad += len(mine) - same + abs(len(mine) - len(theirs))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
