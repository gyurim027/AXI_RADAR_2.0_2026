"""재발 표시(C-10)를 DB에 저장된 값만으로 처음부터 다시 계산한다. 원문은 쓰지 않는다.

쓰는 때: 달을 시간 순서대로 올리지 못했을 때, AI-03이 좌표(gid)를 채운 뒤, 보행_유형이 채워진 뒤.
실행: python scripts/load_recurrence.py [--allow-shared-db]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from load_guard import check_target  # noqa: E402

from app.core import db  # noqa: E402
from app.services.load.recurrence import recompute_recurrence  # noqa: E402
from app.services.load.store import MySQLStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-shared-db", action="store_true")
    a = ap.parse_args()
    target = check_target(a.allow_shared_db)
    con = db.raw_connection()
    try:
        store = MySQLStore(con)
        marked, touched = recompute_recurrence(store, f"재발 다시 계산 {date.today().isoformat()}")
        store.commit()
    except Exception as e:
        con.rollback()
        print(f"재발 다시 계산 실패 ({type(e).__name__}). 되돌렸습니다.")
        return 2
    finally:
        con.close()
    print(f"DB {target} · 재발 표시 {marked}건 · 바뀐 민원 {touched}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
