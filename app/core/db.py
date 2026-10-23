"""공용 DB 연결 (W05-03 골격 3번). 모든 기능이 이 파일 하나로 DB에 붙는다.

쓰는 법
    from app.core import db

    with db.connect() as con:                      # 읽고 쓰기 (자동 커밋 꺼짐 → 끝에 con.commit())
        with con.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM grid_cell")
            print(cur.fetchone()["n"])

    rows = db.read_only("SELECT run_id FROM priority_run WHERE run_id = %s", (1,))   # 읽기 전용 거래로 한 번 조회

- 접속 정보는 .env의 RADAR_DB_* 에서만 읽는다 (app/core/config.py).
- 값은 항상 %s 자리표시자로 넘긴다. SQL 문자열에 값을 직접 이어 붙이지 않는다.
- 결과 행은 dict (칸 이름 → 값). 칸 이름은 SQL v2의 영문 snake_case.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from app.core.config import get_settings


class DbNotConfigured(RuntimeError):
    """RADAR_DB_HOST(또는 RADAR_DB_SOCKET)·RADAR_DB_USER가 없을 때."""


def is_configured() -> bool:
    return get_settings().db.configured


def raw_connection():
    """pymysql 연결 하나를 만든다. 닫는 것은 부른 쪽 책임 (보통은 connect()를 쓴다)."""
    import pymysql
    from pymysql.cursors import DictCursor

    s = get_settings().db
    if not s.configured:
        raise DbNotConfigured("DB 접속 정보가 없습니다. .env의 RADAR_DB_HOST·RADAR_DB_USER를 확인하세요.")
    kw: dict[str, Any] = dict(
        user=s.user, password=s.password, database=s.name, charset="utf8mb4",
        cursorclass=DictCursor, autocommit=False, local_infile=False,
        connect_timeout=s.connect_timeout, read_timeout=s.read_timeout, write_timeout=s.read_timeout,
    )
    if s.socket:
        kw["unix_socket"] = s.socket
    else:
        kw.update(host=s.host, port=s.port)
    return pymysql.connect(**kw)


@contextmanager
def connect() -> Iterator[Any]:
    """연결을 열고, 블록이 끝나면 닫는다. 오류가 나면 되돌린다(rollback)."""
    con = raw_connection()
    try:
        yield con
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def read_only(sql: str, args: Sequence[Any] | None = None) -> list[dict]:
    """읽기 전용 거래(START TRANSACTION READ ONLY) 안에서 SELECT 한 번. 쓰기 문장은 DB가 거부한다."""
    with connect() as con:
        try:
            with con.cursor() as cur:
                cur.execute("START TRANSACTION READ ONLY")
                cur.execute(sql, args or ())
                return list(cur.fetchall())
        finally:
            con.rollback()


def ping() -> bool:
    """연결이 되는지만 확인 (/health/db). 실패 이유는 밖으로 내보내지 않는다."""
    try:
        read_only("SELECT 1 AS ok")
        return True
    except Exception:
        return False
