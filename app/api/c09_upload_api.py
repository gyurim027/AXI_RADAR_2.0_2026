"""C-09 민원 파일 등록: RADAR 운영자가 성남데이터넷 '민원 상세정보 현황' 한 달치 엑셀을 올린다.

POST /api/c09/uploads?source=…&refDate=…&periodStart=…&periodEnd=…[&dataName=…][&isOfficialRaw=…][&fileName=…]
본문 = xlsx 파일 그대로 (multipart 아님: python-multipart 없이 동작). 파일은 디스크에 저장하지 않는다.

- 출처·기준일·기간이 없으면 올릴 수 없다. 기간은 한 달.
- 로그인(I-01)이 붙기 전까지는 이 PC(127.0.0.1)에서 온 요청만 받는다.
- 응답·로그에 민원 원문을 넣지 않는다.
"""
from __future__ import annotations

import threading
from datetime import date

from fastapi import APIRouter, Query, Request
from starlette.concurrency import run_in_threadpool

from app.core import db
from app.core.responses import ApiError
from app.services.load.pipeline import UploadMeta, run_load
from app.services.load.reader import LoadFileError
from app.services.load.store import MySQLStore

router = APIRouter(prefix="/api/c09", tags=["C-09 민원 파일 등록"])

MAX_BYTES = 100 * 1024 * 1024
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
OFFICIAL = {"공식 원본", "가공본", "미확인"}
_lock = threading.Lock()                        # 같은 달을 동시에 올려 서로 덮어쓰지 않게 한 번에 하나씩


def _date(name: str, value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(422, "invalid_date", f"{name}은 YYYY-MM-DD 형식이어야 합니다.")


def _load_sync(data: bytes, file_name: str, meta: UploadMeta):
    con = db.raw_connection()
    try:
        with _lock:
            return run_load(data, file_name, meta, MySQLStore(con))
    finally:
        con.close()


@router.post("/uploads", status_code=201)
async def upload_complaints(
    request: Request,
    source: str = Query(..., min_length=1, max_length=300, description="제공 기관·받은 곳 (필수)"),
    ref_date: str = Query(..., alias="refDate", description="자료 기준일 YYYY-MM-DD (필수)"),
    period_start: str = Query(..., alias="periodStart", description="민원 접수 기간 시작 (그 달 1일)"),
    period_end: str = Query(..., alias="periodEnd", description="민원 접수 기간 끝 (그 달 말일)"),
    data_name: str | None = Query(None, alias="dataName", max_length=200),
    is_official_raw: str = Query("가공본", alias="isOfficialRaw", description="공식 원본 / 가공본 / 미확인"),
    file_name: str = Query("민원 상세정보 현황.xlsx", alias="fileName", max_length=200),
):
    if request.client and request.client.host not in LOCAL_HOSTS:
        raise ApiError(403, "forbidden", "로그인 기능이 붙기 전에는 이 PC에서만 올릴 수 있습니다.")
    if not db.is_configured():
        raise ApiError(503, "db_not_configured", "DB 접속 정보가 없습니다.")
    if is_official_raw not in OFFICIAL:
        raise ApiError(422, "invalid_input", "공식 원본 여부는 공식 원본 · 가공본 · 미확인 중 하나입니다.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise ApiError(413, "too_large", "파일이 너무 큽니다.")
    data = await request.body()
    if not data:
        raise ApiError(400, "empty_file", "파일 내용이 없습니다.")
    if len(data) > MAX_BYTES:
        raise ApiError(413, "too_large", "파일이 너무 큽니다.")

    start = _date("periodStart", period_start)
    meta = UploadMeta(
        data_name=data_name or f"민원 {start.year}년 {start.month}월 (성남데이터넷 민원 상세정보 현황)",
        source=source, ref_date=_date("refDate", ref_date), period_start=start,
        period_end=_date("periodEnd", period_end), is_official_raw=is_official_raw)
    try:
        res = await run_in_threadpool(_load_sync, data, file_name, meta)
    except LoadFileError as e:
        status = 422 if e.code in ("check_failed", "period_mismatch") else 400
        raise ApiError(status, e.code, e.message)
    except db.DbNotConfigured:
        raise ApiError(503, "db_not_configured", "DB 접속 정보가 없습니다.")
    except Exception:
        raise ApiError(500, "load_failed", "적재하지 못했습니다. 업로드 기록의 검사 결과를 확인하세요.")
    return {
        "upload_id": res.upload_id, "rows": res.rows, "check_result": "통과",
        "new": res.counts.new, "existing": res.counts.existing, "updated": res.counts.updated,
        "change_rows": res.counts.change_rows, "missing": res.counts.missing,
        "warnings": res.warnings, "remark": res.remark,
    }
