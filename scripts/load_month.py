"""한 달치 민원 파일 하나를 적재한다 (C-09 API와 같은 흐름). 건수만 출력하고 원문은 출력하지 않는다.

실행 (저장소 루트):
    python scripts/load_month.py <xlsx 파일> --month 2026-09 --source "성남데이터넷 연도별 민원 현황 (공공누리 제1유형)" --ref-date 2026-09-30

- DB 접속은 .env의 RADAR_DB_*. 로컬 DB가 아니면 --allow-shared-db 없이는 멈춘다.
- --rerun-ai01: 이미 AI-01 결과가 있는 민원도 다시 돌린다 (모델을 바꿨을 때).
"""
from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from load_guard import check_target  # noqa: E402

from app.core import db  # noqa: E402
from app.services.load.pipeline import UploadMeta, run_load  # noqa: E402
from app.services.load.reader import LoadFileError  # noqa: E402
from app.services.load.store import MySQLStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--month", required=True, help="YYYY-MM (민원 접수 기간 = 그 달 1일~말일)")
    ap.add_argument("--source", required=True)
    ap.add_argument("--ref-date", required=True, help="자료 기준일 YYYY-MM-DD")
    ap.add_argument("--name", help="자료 이름 (기본: 민원 YYYY년 M월)")
    ap.add_argument("--official", default="가공본", choices=["공식 원본", "가공본", "미확인"])
    ap.add_argument("--rerun-ai01", action="store_true")
    ap.add_argument("--allow-shared-db", action="store_true")
    a = ap.parse_args()

    target = check_target(a.allow_shared_db)
    y, m = (int(x) for x in a.month.split("-"))
    meta = UploadMeta(data_name=a.name or f"민원 {y}년 {m}월 (성남데이터넷 민원 상세정보 현황)", source=a.source,
                      ref_date=date.fromisoformat(a.ref_date), period_start=date(y, m, 1),
                      period_end=date(y, m, calendar.monthrange(y, m)[1]), is_official_raw=a.official)
    path = Path(a.file)
    con = db.raw_connection()
    try:
        res = run_load(path.read_bytes(), path.name, meta, MySQLStore(con), rerun_ai01=a.rerun_ai01)
    except LoadFileError as e:
        print(f"적재 실패: [{e.code}] {e.message}")
        return 1
    except Exception as e:                       # 예외 상세에 값이 섞일 수 있어 종류만 보여 준다
        print(f"적재 실패: 예상하지 못한 오류 ({type(e).__name__}). 84 업로드 기록의 검사 결과를 확인하세요.")
        return 2
    finally:
        con.close()
    c = res.counts
    print(f"DB {target} · 업로드 {res.upload_id} · 민원 {res.rows}건 · 신규 {c.new} · 기존 {c.existing} · 갱신 {c.updated}(80번 {c.change_rows}줄) · 빠짐 {c.missing}")
    print(f"AI-01 ok {res.ai.ok} (가짜 {res.ai.stub}) · 가림 실패 {res.ai.mask_failed} · 오류 {res.ai.error}")
    for w in res.warnings:
        print("경고:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
