"""AI-07 근거 설명문 API (공통 서버용으로 옮김. 원래 backend/ai07/db_server.py·server.py).

주소는 그대로다.
  GET  /api/ai07/health
  GET  /api/ai07/db/runs
  GET  /api/ai07/db/candidates?run_id=…
  GET  /api/ai07/db/explanation?run_id=…&gid=…
  POST /api/ai07/explain            (가상 입력 시험, DB·외부 API 안 씀)
지킨 것: DB는 읽기 전용 거래 + 고정 SELECT만, 외부 AI 호출 없음, 요청·응답 본문을 로그에 남기지 않음,
        오류에 비밀번호·SQL·조회 결과를 넣지 않음, 로그인이 붙기 전까지는 이 PC(127.0.0.1)에서 온 요청만 받음.
바뀐 것: 포트 8007 → 공통 서버 8000, 접속 정보 화면 입력 → .env, 오류 모양 → 공통 {"error": {...}},
        화면에 주는 응답 칸 이름 → camelCase (공통 규칙, X-Response-Case: snake 이면 원래 이름).
"""
import json

from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.responses import ApiError
from app.services.ai07.mock_input import MAX_BYTES, explain_request, run_id_arg
from app.services.ai07.read_only_db import core_repository

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def local_only(request: Request):
    """로그인(I-01)이 붙기 전까지: 이 PC에서 온 요청, 허용된 화면 주소만 받는다 (원래 safe_origin)."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    origin = request.headers.get("origin")
    if host not in LOCAL_HOSTS or (origin is not None and origin not in get_settings().cors_origins):
        raise ApiError(403, "local_access_only", "이 PC에서만 열 수 있습니다")


def get_repository():
    """시험에서는 app.dependency_overrides[get_repository]로 가짜 저장소를 넣는다."""
    return core_repository()


router = APIRouter(prefix="/api/ai07", tags=["AI-07 근거 설명문"], dependencies=[Depends(local_only)])


def _read(action):
    try:
        return action()
    except ValueError:
        raise ApiError(400, "invalid_input_or_stored_value", "입력이나 저장된 값이 올바르지 않습니다")
    except ApiError:
        raise
    except Exception:
        # 비밀번호·서버 오류 상세·SQL 본문·조회 결과를 내보내지 않는다.
        raise ApiError(503, "db_read_failed", "DB 조회에 실패했습니다")


def _only(request: Request, allowed: set[str]):
    if set(request.query_params.keys()) != allowed:
        raise ApiError(404, "not_found", "없는 주소입니다")


@router.get("/health")
def health():
    return {"status": "ok", "external_api_called": False}


@router.get("/db/runs")
def runs(request: Request, repo=Depends(get_repository)):
    _only(request, set())
    return _read(repo.runs)


@router.get("/db/candidates")
def candidates(request: Request, repo=Depends(get_repository)):
    _only(request, {"run_id"})
    return _read(lambda: repo.candidates(run_id_arg(request.query_params.getlist("run_id"))))


@router.get("/db/explanation")
def explanation(request: Request, repo=Depends(get_repository)):
    _only(request, {"run_id", "gid"})

    def go():
        gids = request.query_params.getlist("gid")
        if len(gids) != 1 or not 1 <= len(gids[0]) <= 32:
            raise ValueError("invalid_gid")
        return repo.explanation(run_id_arg(request.query_params.getlist("run_id")), gids[0])
    return _read(go)


@router.post("/explain")
async def explain(request: Request):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise ApiError(415, "json_required", "JSON으로 보내 주세요")
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise ApiError(400, "invalid_request", "요청 형식이 올바르지 않습니다")
    if length <= 0 or length > MAX_BYTES:
        raise ApiError(413, "invalid_size", "요청이 너무 크거나 비어 있습니다")
    raw = await request.body()
    try:
        if len(raw) != length:
            raise ValueError("invalid_size")
        return explain_request(json.loads(raw))
    except (ValueError, TypeError, OverflowError, RecursionError):
        # 원본 입력을 응답에 되돌려 보내지 않는다.
        raise ApiError(400, "invalid_input", "입력이 올바르지 않습니다")


# 2026-10-22: AI-07 가상 E-02/E-03/F-06/H-04 시험 연결.
# 공통 app/main.py를 바꾸지 않고 기존 AI-07 router에 포함한다.
from app.api.ai07_synthetic_api import router as synthetic_router
router.include_router(synthetic_router)
