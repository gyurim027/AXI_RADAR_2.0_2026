"""공통 응답·오류 형식 (W05-03 골격 5번).

1) 칸 이름: DB·파이썬은 snake_case, 화면에 주는 응답은 camelCase (프론트 목업 기준).
   /api/ 아래 JSON 응답의 영문 snake_case 키만 camelCase로 바꾼다. 값은 바꾸지 않는다.
   - 한글 키, 대문자·하이픈이 든 키(CK-09 등)는 그대로 둔다.
   - 백엔드끼리 원래 이름이 필요하면 요청 머리에 X-Response-Case: snake 를 붙인다.
2) 오류: 모두 {"error": {"status": 404, "code": "not_found", "message": "..."}} 한 모양.
   message에 비밀번호·SQL·원문·예외 상세를 넣지 않는다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")


def to_camel(key: str) -> str:
    if not isinstance(key, str) or not SNAKE.match(key):
        return key
    head, *rest = key.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {to_camel(k): camelize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camelize(v) for v in value]
    return value


class CamelCaseMiddleware(BaseHTTPMiddleware):
    """/api/ 아래 JSON 응답의 키를 camelCase로 바꾼다."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            return response
        if request.headers.get("x-response-case", "").lower() == "snake":
            return response
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            data = json.loads(body)
        except ValueError:
            return _same(response, body)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return JSONResponse(camelize(data), status_code=response.status_code, headers=headers)


def _same(response, body: bytes):
    from starlette.responses import Response
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    return Response(body, status_code=response.status_code, headers=headers, media_type=response.media_type)


class ApiError(Exception):
    """기능 코드에서 공통 모양의 오류를 내고 싶을 때: raise ApiError(400, "invalid_run", "실행 번호 형식이 틀립니다")"""

    def __init__(self, status: int, code: str, message: str = ""):
        self.status, self.code, self.message = status, code, message or code


_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
          409: "conflict", 413: "too_large", 415: "unsupported_media_type", 422: "invalid_input", 500: "server_error",
          503: "unavailable"}


def error_body(status: int, code: str, message: str) -> dict:
    return {"error": {"status": status, "code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError):
        return JSONResponse(error_body(exc.status, exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def _http_error(_req: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else _CODES.get(exc.status_code, "error")
        return JSONResponse(error_body(exc.status_code, _CODES.get(exc.status_code, f"http_{exc.status_code}"), message),
                            status_code=exc.status_code, headers=getattr(exc, "headers", None))

    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def _starlette_error(_req: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else _CODES.get(exc.status_code, "error")
        return JSONResponse(error_body(exc.status_code, _CODES.get(exc.status_code, f"http_{exc.status_code}"), message),
                            status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()]
        return JSONResponse(error_body(422, "invalid_input", "입력 형식이 맞지 않습니다: " + ", ".join(f for f in fields if f)),
                            status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, _exc: Exception):
        return JSONResponse(error_body(500, "server_error", "서버 오류"), status_code=500)
