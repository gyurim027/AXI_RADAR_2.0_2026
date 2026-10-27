"""AI-03 좌표 반영 (A-07·C-06, 세은): out/ai03/*_update.csv → 공용 DB의 좌표 칸. 기본은 미리 보기, --apply를 줘야 쓴다.

쓰는 것: 좌표(lat·lon)와 격자(gid) 등 위치 칸만. 좌표가 **빈 행에만** 쓰고, 이미 값이 있는 행은 건드리지 않는다.
        민원(79)의 구·행정동은 비어 있을 때만 채운다. 점수·순위·다른 표는 건드리지 않는다.
안전장치: 미리 보기 → 백업 CSV → 표 하나를 한 거래로 반영(한 행이라도 계획과 다르면 전부 되돌림) → 반영 뒤 다시 세어 확인.
        반영은 85 job_run에 기록된다 (미리 보기는 DB를 전혀 안 바꿈).

사용법 (저장소 루트, 표는 parking · signal · police · complaint)
  uv run python -m scripts.ai03_apply police    out/ai03/police_update.csv                 # 미리 보기
  uv run python -m scripts.ai03_apply police    out/ai03/police_update.csv --apply         # 반영 (먼저 HeidiSQL로 백업해 두세요)
  uv run python -m scripts.ai03_apply police    --rollback out/ai03/backup_police_<시각>.csv --apply   # 되돌리기 (--apply 없으면 미리 보기)
옵션: --skip-problems  '반영' 말고 다른 상태(DB에 없음·격자 없음 등)가 있어도 '반영' 행만 쓴다 · --no-gid-check  좌표↔gid 검사 끄기
반영 순서(행이 적은 표부터): police → signal → complaint → parking. 표 하나 반영하고 건수를 확인한 뒤 다음으로 간다.
"""
import argparse
import sys
from pathlib import Path


def main():
    from app.services.ai03 import apply_updates as A
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("table", choices=A.TABLES)
    ap.add_argument("file", nargs="?", help="*_update.csv (v2 칸 이름)")
    ap.add_argument("--apply", action="store_true", help="실제로 DB에 쓴다 (없으면 미리 보기)")
    ap.add_argument("--rollback", metavar="BACKUP_CSV", help="백업 CSV로 되돌린다")
    ap.add_argument("--skip-problems", action="store_true")
    ap.add_argument("--no-gid-check", action="store_true")
    a = ap.parse_args()

    from app.core import db
    if not db.is_configured():
        sys.exit("DB 접속 정보가 없습니다 (.env RADAR_DB_*).")
    from app.services.ai03 import config as C
    out = Path(C.OUT)
    store = A.MySqlStore()

    if a.rollback:
        n, skip = A.rollback_from_backup(a.table, a.rollback, store, apply=a.apply)
        print(f"되돌릴 수 있는 행 {n:,} · 건너뛸 행 {skip:,} (그 뒤에 값이 바뀐 행은 건드리지 않음)")
        print("되돌렸습니다." if a.apply else "미리 보기입니다. 실제로 되돌리려면 --apply를 붙이세요.")
        return
    if not a.file:
        sys.exit("반영할 *_update.csv 파일을 주세요.")

    stamp = A.stamp_now()
    plan = A.build_plan(a.table, a.file, store, check_gid=not a.no_gid_check)
    print(A.format_plan(plan))
    print(f"  계획 표 → {A.write_plan_csv(plan, out, stamp)}")
    problems = {k: v for k, v in plan.summary().items() if k not in (A.OK, A.HAS_COORD)}
    if not plan.ok_rows():
        if plan.count(A.HAS_COORD) and not problems:
            print("\n반영할 행이 없습니다 — 파일의 행이 모두 이미 좌표가 있어서(이미 반영했거나 그새 채워짐) 건너뜁니다.")
            return
        sys.exit("반영할 행이 없습니다. 위의 상태를 확인하세요.")
    if problems and not a.skip_problems:
        sys.exit(f"'반영'이 아닌 상태가 있습니다 {problems}. 계획 표를 확인하고, 괜찮으면 --skip-problems를 붙이세요.")
    if not a.apply:
        print("\n미리 보기입니다 — DB는 바뀌지 않았습니다. 실제로 쓰려면 --apply를 붙이세요 (먼저 백업).")
        return

    from app.core.job_run import track
    backup = A.write_backup(plan, out, stamp)
    print(f"\n백업 → {backup}")
    with track("좌표", f"AI-03 DB 반영 {plan.table}", module="AI-03") as job:
        n = A.apply_plan(plan, A.MySqlStore())
        job.rows(n)
        got = A.verify_applied(plan, A.MySqlStore())
        job.log(f"{plan.table} {n}행 반영, 다시 세어 보니 {got}행")
        if got != n:
            job.warn(f"반영 {n}행인데 확인 {got}행 — 직접 확인하세요")
    print(f"반영 {n:,}행 · 다시 세어 보니 {got:,}행" + ("" if got == n else "  ← 다릅니다! 확인하세요"))
    print(f"되돌리려면: uv run python -m scripts.ai03_apply {a.table} --rollback {backup} --apply")


if __name__ == "__main__":
    main()
