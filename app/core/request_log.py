"""공통 요청 로그 (W05-03 골격 9번, 1차).

요청 하나에 JSON 한 줄을 남긴다. 칸:
  ts · request_id · method · path · status · duration_ms · module · user_id · role · error_code
남기지 않는 것: 요청·응답 본문, 쿼리 문자열(검색어·좌표가 들어갈 수 있음), 비밀번호·토큰, 민원 원문, 예외 상세 (ISS-032)
- request_id는 응답 머리 X-Request-ID로도 돌려준다. LLM 모듈 로그(W05-05)도 이 값을 같이 남겨 이어 붙인다.
- user_id·role은 로그인(I-01)이 붙으면 request.state.user에서 채운다. 지금은 빈 값.
- 이 로그는 운영 확인용이다. 법정 접속기록(I-04, 70 access_audit)은 따로 남긴다.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("radar.request")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def module_of(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[1] if len(parts) > 1 and parts[0] == "api" else (parts[0] or "root")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        start = time.perf_counter()
        status, error_code = 500, None
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        except Exception as exc:                      # 본문·상세는 남기지 않고 종류만
            error_code = type(exc).__name__
            raise
        finally:
            user = getattr(request.state, "user", None) or {}
            logger.info(json.dumps({
                "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "request_id": rid, "method": request.method, "path": request.url.path,
                "status": status, "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "module": module_of(request.url.path),
                "user_id": user.get("user_id"), "role": user.get("role"), "error_code": error_code,
            }, ensure_ascii=False))
