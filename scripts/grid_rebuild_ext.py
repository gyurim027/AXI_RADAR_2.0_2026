"""05 grid_feature EXT_ 21열 · 06 grid_feature_ng 센 값 6열을 DB 표에서 다시 채운다 (B-02 재계산, 세은).

실행 (저장소 루트, PowerShell) — .env의 RADAR_DB_*가 다시 채울 DB를 가리켜야 함
    uv run python -m scripts.grid_rebuild_ext            # 미리 보기: 지금 값과 칸마다 비교만 (DB 안 바꿈)
    uv run python -m scripts.grid_rebuild_ext --apply    # 다른 칸만 UPDATE (한 거래로, 실패하면 전부 되돌림)

순서: 세은 05 다시 넣기(83열) → 이 스크립트 --apply → 83 src_road_hazard 파일 다시 실행(COND_ 포트홀·시선유도봉 4열) → 07~10 판정 → 진규님께 알림
- 원천 표(39·41·42·45·50·51·52, 07~09 판정)가 바뀌면 여기서 새 값이 나온다
- 한 번 조사한 자료 4칸(2022 후보지·2025 도면·2022 조사 범위 2칸)은 data/grid/ext_carry_05_v2_1.csv 값을 이어 쓴다
- 06의 보도 면적·폭 5칸은 수치지형도 도형이 있어야 해서 건드리지 않는다(은경, 도면이 2025년 판 그대로면 안 바뀜)
- 자세한 규칙: docs/grid/ext_columns.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

try:
    from app.core.job_run import track
except ImportError:                     # 공통 구조 합치기 전 브랜치
    from contextlib import contextmanager

    @contextmanager
    def track(*_a, **_k):
        class _J:
            def log(self, *_): pass
            def rows(self, *_): pass
        yield _J()

from app.core import db
from app.services.grid.ext_columns import (COLUMNS, NG_CARRY, NG_COLUMNS, compare_ng_with_current, compare_with_current,
                                           compute, compute_ng)

OUT = Path(__file__).resolve().parents[1] / "out" / "grid"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="05 EXT_ · 06 EXTNG_ 센 값 다시 채우기")
    ap.add_argument("--apply", action="store_true", help="다른 칸을 DB에 반영")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    with track("산정", "격자 EXT_ 열 다시 채우기", module="B-02") as job:
        ext, ng = compute(), compute_ng()
        r05, r06 = compare_with_current(ext), compare_ng_with_current(ng)
        diff05 = {c: v["diff"] for c, v in r05.items() if v["diff"]}
        diff06 = {c: v["diff"] for c, v in r06.items() if v["diff"]}
        print("05 EXT_ 21열: 다른 칸", diff05 or "없음")
        print("06 EXTNG_ 센 값 6열: 다른 칸", diff06 or "없음")
        path = OUT / f"ext_compare_{datetime.datetime.now():%y%m%d_%H%M}.json"
        path.write_text(json.dumps({"grid_feature": r05, "grid_feature_ng": r06}, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
        print("자세한 비교:", path)
        job.log(f"05 다른 칸 {sum(diff05.values())}, 06 다른 칸 {sum(diff06.values())}")
        if not args.apply:
            print("미리 보기만 했습니다. 반영하려면 --apply")
            return 0

        cur05 = {r["ID_gid"]: r for r in db.read_only("SELECT ID_gid, " + ", ".join(f"`{c}`" for c in COLUMNS) + " FROM grid_feature")}
        ng_cols = [c for c in NG_COLUMNS if c not in NG_CARRY]
        cur06 = {r["ID_gid"]: r for r in db.read_only("SELECT ID_gid, " + ", ".join(f"`{c}`" for c in ng_cols) + " FROM grid_feature_ng")}
        n = 0
        with db.connect() as con:
            with con.cursor() as cur:
                for gid, row in ext.items():
                    if gid not in cur05:
                        continue
                    ch = {c: v for c, v in row.items() if str(cur05[gid].get(c)) != str(v)}
                    if ch:
                        cur.execute("UPDATE grid_feature SET " + ", ".join(f"`{c}` = %s" for c in ch) + " WHERE ID_gid = %s",
                                    (*ch.values(), gid)); n += 1
                for gid, row in ng.items():
                    if gid not in cur06:
                        continue
                    ch = {c: row[c] for c in ng_cols if str(cur06[gid].get(c)) != str(row[c])}
                    if ch:
                        cur.execute("UPDATE grid_feature_ng SET " + ", ".join(f"`{c}` = %s" for c in ch) + " WHERE ID_gid = %s",
                                    (*ch.values(), gid)); n += 1
            con.commit()
        job.rows(n)
        print(f"{n}칸(행)을 고쳤습니다. 다음: 83 src_road_hazard 파일 다시 실행 → 07~10 판정 → 진규님께 알림")
    return 0


if __name__ == "__main__":
    sys.exit(main())
