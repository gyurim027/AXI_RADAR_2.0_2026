"""A-11 법령 개정 확인 실행.

새로 받은 법령 원문 폴더(국가법령정보센터_현행법령·_행정규칙·_자치법규·정책자료 하위 폴더 구조)를 지금 색인과 비교한다.

실행 (저장소 루트, PowerShell)
    uv run python -m scripts.standards_check_law_revision --new-src "D:\\RADAR\\법령원문_2027상반기"           # 비교만
    uv run python -m scripts.standards_check_law_revision --new-src "D:\\RADAR\\법령원문_2027상반기" --apply   # 비교 + 색인 바꾸기

- 비교 결과: out/standards/law_revision_<날짜>.json (바뀐 법령·조문, 확인할 57 criterion 행)
- --apply: 새 docs·chunks로 data/ai05를 바꾸고 색인·평가를 다시 만든다 (원문 폴더는 저장소에 올리지 않음)
- 실행 기록(85 job_run)을 '색인'으로 남긴다 (SQL v2.1 뒤). 없어도 실행은 된다.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

try:                                    # 실행 기록 (공통 구조 feature/w05-core). 합치기 전 브랜치에서도 돌게
    from app.core.job_run import track
except ImportError:                     # pragma: no cover
    from contextlib import contextmanager

    @contextmanager
    def track(*_a, **_k):
        class _J:
            def log(self, *_): pass
            def rows(self, *_): pass
        yield _J()
from app.services.ai05 import chunk, extract
from app.services.standards.revision import compare, read_chunks, rows_to_save

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "ai05"
OUT = ROOT / "out" / "standards"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A-11 법령 개정 확인")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--new-src", help="새 법령 원문 폴더")
    src.add_argument("--new-chunks", help="이미 만든 새 chunks.jsonl (시험용)")
    ap.add_argument("--date", default=datetime.date.today().isoformat(), help="기준일 (시행 전 판단)")
    ap.add_argument("--apply", action="store_true", help="비교 뒤 색인을 새 원문으로 바꾸기")
    ap.add_argument("--no-save", action="store_true", help="89 standard_change에 남기지 않기 (기본: DB가 있으면 남김)")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%y%m%d_%H%M")
    with track("색인", f"법령 개정 확인 ({args.date})", module="A-11") as job:
        _remember(job, "A-11", sys.argv[1:] if argv is None else argv)   # 운영 화면 '다시 실행'(I-06)용 입력 한 줄
        if args.new_src:
            new_docs, new_chunks = OUT / f"new_docs_{stamp}.jsonl", OUT / f"new_chunks_{stamp}.jsonl"
            extract.main(args.new_src, new_docs)
            chunk.main(new_docs, new_chunks, args.date)
            job.log("새 원문에서 조문 조각을 만들었습니다")
        else:
            new_docs, new_chunks = None, Path(args.new_chunks)
        criteria = json.loads((D / "criterion.json").read_text(encoding="utf-8"))
        rep = compare(read_chunks(D / "chunks.jsonl"), read_chunks(new_chunks), criteria)
        rep["checked_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        rep["base_date"] = args.date
        path = OUT / f"law_revision_{stamp}.json"
        path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        s = rep["summary"]
        job.log(f"법령 {s['laws_checked']}개 중 {s['laws_changed']}개, 조문 {s['articles_changed']}곳 바뀜")
        job.rows(s["articles_changed"])

        print(f"법령 {s['laws_checked']}개 비교 → 바뀐 법령 {s['laws_changed']}개 · 바뀐 조문 {s['articles_changed']}곳")
        for law in rep["laws"]:
            print(f"  - {law['name']}: {law['status']} ({law['old_effective']} → {law['new_effective']})")
        if s["criteria_to_check"]:
            print("  바뀐 조를 직접 쓰는 법령 색인(57 criterion):", ", ".join(s["criteria_to_check"]))
        if s["criteria_same_law"]:
            print("  같은 법령을 쓰는 행(참고):", ", ".join(s["criteria_same_law"]))
        print("자세한 결과:", path)
        _save(rows_to_save(rep), getattr(job, "run_id", None), args.no_save)

        if args.apply and s["laws_changed"]:
            if new_docs is None:
                print("--apply는 --new-src와 같이 써 주세요 (원문에서 다시 만들어야 함)")
                return 1
            shutil.copyfile(new_docs, D / "docs.jsonl")
            shutil.copyfile(new_chunks, D / "chunks.jsonl")
            from scripts import ai05_build_index
            ai05_build_index.main(["--from-chunks"])
            job.log("색인을 새 원문으로 바꿨습니다")
            print("색인을 바꿨습니다. 서버를 다시 켜면 새 색인을 씁니다.")
    return 0


def _save(rows, run_id, no_save) -> None:
    """89 standard_change(규정 변경 기록)에 남기고, 걸리는 담당 부서 표(87)를 붙인다. DB가 없으면 건너뜀."""
    from app.core import db
    if no_save or not rows or not db.is_configured():
        return
    from app.services.standards.dept_draft import link_jurisdiction
    from app.services.standards.repository import get_repository
    repo = get_repository()
    link_jurisdiction(rows, repo.jurisdiction())
    print(f"규정 변경 기록(89)에 {repo.save_changes(rows, run_id)}줄 남겼습니다")


def _remember(job, module, argv) -> None:
    """86 실행 로그에 다시 실행용 입력을 남긴다 (app/services/standards/rerun_hooks.py). 실패해도 명령은 계속."""
    try:
        from app.services.standards.rerun_hooks import remember
        remember(job, module, argv)
    except Exception:                       # pragma: no cover - 실행 기록 없이 도는 브랜치·환경
        pass


if __name__ == "__main__":
    sys.exit(main())
