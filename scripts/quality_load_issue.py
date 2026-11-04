"""A-06·A-08 결과를 data_issue(92)에 넣는다 (세은). 기본은 미리 보기, --apply를 줘야 쓴다.

입력: scripts.quality_anomaly(A-06)·scripts.quality_same_facility(A-08)가 만든 공통 15칸 CSV
      (out/grid/a06_flags.csv · out/grid/a08_groups.csv). A-05는 진이님이 넣으므로 이 도구로는 넣지 않는다.
쓰는 것: data_issue 한 표뿐. 같은 문제는 한 줄(UNIQUE), 이미 있는 줄은 값·찾은 시각만 고치고 운영자 칸(확인·처리)은 그대로 둔다.
안전장치: 미리 보기 → 백업 CSV → 한 거래로 반영(한 줄이라도 막히면 전부 되돌림) → 다시 세어 확인. 반영은 85 job_run에 기록된다.

사용법 (저장소 루트)
  uv run python -m scripts.quality_load_issue A-06 out/grid/a06_flags.csv                    # 미리 보기
  uv run python -m scripts.quality_load_issue A-06 out/grid/a06_flags.csv --apply            # 반영
  uv run python -m scripts.quality_load_issue A-06 --rollback out/quality/backup_issue_A-06_<시각>.csv --apply
옵션: --prune-stale  이번 검사 파일에 아예 없고 운영자 칸(확인·처리)이 빈 같은 검사 기능의 기존 줄을 지운다. 줄 때만 지운다.
        운영자 칸이 있는 줄·A-05 줄은 안 지운다. 기존 줄의 10%(최소 50줄)를 넘으면 멈춘다. 지운 줄은 백업에 남아 --rollback으로 되살린다
      --prune-max N  정리 상한을 N줄로 올린다 (파일이 맞는 걸 확인한 뒤에만)
      --exclude 표:검사이름앞부분  그 줄은 넣지 않음 (여러 번 가능, 예: --exclude "src_parking_enforce_place:③")
      --skip-problems  '새로·다시 확인·값 바뀜' 말고 다른 상태(check_fn 다름·길이 초과·upload_id 없음 등)가 있어도 나머지만 쓴다
"""
import argparse
import sys
from pathlib import Path


def main():
    from app.services.quality import issue_load as L
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("fn", choices=L.MINE, help="검사 기능 (A-06 · A-08)")
    ap.add_argument("file", nargs="?", help="공통 15칸 CSV")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", metavar="BACKUP_CSV")
    ap.add_argument("--exclude", action="append", default=[], metavar="표:검사이름앞부분")
    ap.add_argument("--skip-problems", action="store_true")
    ap.add_argument("--prune-stale", action="store_true")
    ap.add_argument("--prune-max", type=int, metavar="N")
    a = ap.parse_args()

    from app.core import db
    from app.core.config import ROOT
    if not db.is_configured():
        sys.exit("DB 접속 정보가 없습니다 (.env RADAR_DB_*).")
    out = ROOT / "out" / "quality"
    out.mkdir(parents=True, exist_ok=True)

    if a.rollback:
        d, u, b, s = L.rollback_from_backup(a.fn, a.rollback, L.MySqlStore(), apply=a.apply)
        print(f"지울 줄 {d:,} · 옛 값으로 되돌릴 줄 {u:,} · 되살릴 줄(정리로 지웠던 줄) {b:,} · 건너뛸 줄 {s:,} (그 뒤에 운영자가 확인·처리를 적은 줄은 건드리지 않음)")
        print("되돌렸습니다." if a.apply else "미리 보기입니다. 실제로 되돌리려면 --apply를 붙이세요.")
        return
    if not a.file:
        sys.exit("넣을 CSV 파일을 주세요.")

    stamp = L.stamp_now()
    excl = [tuple(x.split(":", 1)) for x in a.exclude if ":" in x]
    if len(excl) != len(a.exclude):
        sys.exit("--exclude는 표:검사이름앞부분 모양이어야 합니다 (예: src_parking_enforce_place:③)")
    plan = L.build_plan(a.fn, a.file, L.MySqlStore(), exclude=excl)
    print(L.format_plan(plan, prune=a.prune_stale))
    print(f"  계획 표 → {L.write_plan_csv(plan, out, stamp)}")
    if plan.stale:
        print(f"  안 나온 줄 목록 → {L.write_stale_csv(plan, out, stamp, prune=a.prune_stale)}")
    if a.prune_stale:
        try:
            L.check_prune(plan, a.prune_max)
        except ValueError as e:
            sys.exit(str(e))
    problems = {k: v for k, v in plan.summary().items() if k not in L.OKS and k != L.EXCLUDED}
    if not plan.writable():
        sys.exit("넣을 줄이 없습니다. 위의 상태를 확인하세요.")
    if problems and not a.skip_problems:
        sys.exit(f"넣을 수 없는 줄이 있습니다 {problems}. 계획 표를 확인하고, 괜찮으면 --skip-problems를 붙이세요.")
    if not a.apply:
        print("\n미리 보기입니다 — DB는 바뀌지 않았습니다. 실제로 쓰려면 --apply를 붙이세요.")
        return

    from app.core.job_run import track
    backup = L.write_backup(plan, out, stamp, prune=a.prune_stale)
    print(f"\n백업 → {backup}")
    with track("검사", f"{a.fn} 결과를 data_issue에 적재", module=a.fn) as job:
        rid = next((getattr(job, n) for n in ("job_run_id", "run_id", "id") if isinstance(getattr(job, n, None), int)), None)
        n_new, n_upd, n_del = L.apply_plan(plan, L.MySqlStore(), job_run_id=rid, prune=a.prune_stale, prune_max=a.prune_max)
        got = L.verify(plan, L.MySqlStore())
        total, want = L.count_fn(L.MySqlStore(), a.fn), plan.n_existing + n_new - n_del
        job.rows(n_new + n_upd + n_del)
        job.log(f"{a.fn} data_issue 새로 {n_new}줄 · 고침 {n_upd}줄 · 지움 {n_del}줄, 다시 세어 보니 파일의 줄 {got}줄 · 전체 {total}줄")
        if got != n_new + n_upd or total != want:
            job.warn(f"확인이 맞지 않습니다(파일의 줄 {got}/{n_new + n_upd}, 전체 {total}/{want}) — 직접 확인하세요")
    ok = got == n_new + n_upd and total == want
    print(f"새로 {n_new:,}줄 · 고침 {n_upd:,}줄 · 지움 {n_del:,}줄 · 다시 세어 보니 파일의 줄 {got:,}줄 · {a.fn} 전체 {total:,}줄(기대 {want:,})"
          + ("" if ok else "  ← 다릅니다! 확인하세요"))
    print(f"되돌리려면: uv run python -m scripts.quality_load_issue {a.fn} --rollback {backup} --apply")


if __name__ == "__main__":
    main()
