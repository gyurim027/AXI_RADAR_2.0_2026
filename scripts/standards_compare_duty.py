"""A-12 업무분장 변경 확인 + F-05 담당 부서 표 수정안 만들기 실행.

실행 (저장소 루트, PowerShell)
    uv run python -m scripts.standards_compare_duty --old "이전판.hwp" --new "새판.hwp" --name "성남시 사무위임 조례 별표 1"
    uv run python -m scripts.standards_compare_duty --old 이전.hwp --new 새.hwp --jurisdiction 담당부서표.json   # 수정안까지

- 파일: .hwp · .hwpx · .pdf · .txt (AI-05와 같은 방법으로 글자를 뽑음)
- --jurisdiction: 담당 부서 표 JSON 목록 [{id, problem, dept, related, status, basis}]. DB 표가 생기면 DB에서 읽게 바꾼다.
- --not-delegation: 사무위임 별표가 아니라 일반 업무분장 문서일 때 (부서 옮김만 받는 부서로 씀)
- 결과: out/standards/duty_compare_<날짜>.json (바뀐 사무, 보행 관련 먼저, 수정안)
- 수정안은 확정이 아니다. 운영자가 고쳐서 승인 흐름(62 setting_version, I-07)에 올린다.
"""
from __future__ import annotations

import argparse
import datetime
import json
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
from app.services.ai05.extract import READERS
from app.services.standards.dept_draft import link_jurisdiction, make_drafts
from app.services.standards.duty_table import compare, parse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "standards"


def load_duties(path: str):
    """폴더 = 누리집 부서 페이지 묶음(org_pages), 파일 = 사무위임 별표 모양(duty_table)."""
    p = Path(path)
    if p.is_dir():
        from app.services.standards.org_pages import parse_org_folder
        return parse_org_folder(p)
    return parse(read_text(path))


def read_text(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() == ".txt":
        return p.read_text(encoding="utf-8")
    if p.suffix.lower() not in READERS:
        raise SystemExit(f"읽을 수 없는 파일 형식: {p.suffix} (.hwp · .hwpx · .pdf · .txt)")
    return READERS[p.suffix.lower()](p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A-12 업무분장 변경 확인 + F-05 수정안")
    ap.add_argument("--old", required=True, help="이전 판: 사무위임 별표 파일, 또는 누리집 부서 페이지 PDF를 모은 폴더")
    ap.add_argument("--new", required=True, help="새 판: 같은 모양")
    ap.add_argument("--name", default="업무분장", help="문서 이름 (결과·수정안 근거에 씀)")
    ap.add_argument("--jurisdiction", help="담당 부서 표 JSON (있으면 F-05 수정안까지)")
    ap.add_argument("--not-delegation", action="store_true", help="사무위임 별표가 아닌 일반 업무분장 문서")
    ap.add_argument("--no-save", action="store_true", help="89 standard_change에 남기지 않기 (기본: DB가 있으면 남김)")
    ap.add_argument("--no-ai", action="store_true", help="F-05 수정안을 규칙 방식으로만 (공통 LLM f05_extract를 부르지 않음)")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    with track("검사", f"업무분장 변경 확인 ({args.name})", module="A-12") as job:
        old, new = load_duties(args.old), load_duties(args.new)
        job.log(f"이전 판 사무 {len(old)}개, 새 판 사무 {len(new)}개를 읽었습니다")
        rep = compare(old, new, args.name)
        from app.core import db
        rows = None
        if args.jurisdiction:
            rows = json.loads(Path(args.jurisdiction).read_text(encoding="utf-8"))
        elif db.is_configured():                                  # SQL v2.1: 87·88 담당 부서 표
            from app.services.standards.repository import get_repository
            rows = get_repository().jurisdiction()
        if rows is not None:
            link_jurisdiction(rep["changes"], rows)
            rep["drafts"] = make_drafts(rep["changes"], rows, args.name, delegation_annex=not args.not_delegation,
                                        use_ai=not args.no_ai)
            n_ai = sum(1 for d in rep["drafts"] if d.get("method", "").startswith("AI"))
            job.log(f"담당 부서 표 수정안 {len(rep['drafts'])}개를 만들었습니다 (AI {n_ai} · 규칙 {len(rep['drafts']) - n_ai})")
        rep["checked_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        path = OUT / f"duty_compare_{datetime.datetime.now():%y%m%d_%H%M}.json"
        path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        s = rep["summary"]
        job.rows(s["changes"])
        print(f"사무 {s['old_duties']} → {s['new_duties']}개 · 바뀐 곳 {s['changes']}개 (보행 관련 {s['related']}개)")
        for c in rep["changes"][:15]:
            mark = "★" if c["related"] else " "
            print(f" {mark} [{c['change']}] {c['where']}: {c['duty'][:60]}")
        if rep["depts"]["new"] or rep["depts"]["gone"]:
            print("  새 부서:", rep["depts"]["new"], "· 없어진 부서:", rep["depts"]["gone"])
        if "drafts" in rep:
            for d in rep["drafts"]:
                print(f"  수정안 [{d.get('method', '규칙')}] {d['jur_id']} {d['problem']}: {d['from']} → {d['to']}"
                      + (f" (도로 종류 {d['road_type']})" if d.get("road_type") else ""))
        print("자세한 결과:", path)
        if not args.no_save and db.is_configured() and rep["changes"]:
            from app.services.standards.repository import get_repository
            n = get_repository().save_changes(rep["changes"], getattr(job, "run_id", None))
            print(f"규정 변경 기록(89)에 {n}줄 남겼습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
