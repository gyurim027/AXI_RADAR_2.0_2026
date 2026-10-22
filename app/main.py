"""RADAR 2.0 공통 서버 (W05-03). 모든 기능의 API를 이 서버 하나(포트 8000)에 붙인다.

실행 (저장소 루트, PowerShell)
    uv run uvicorn app.main:app --port 8000        # http://127.0.0.1:8000/docs 에서 모든 API 확인

새 기능 붙이기: app/api/<기능>_<이름>_api.py 에 router = APIRouter(prefix="/api/<기능>") 를 만들고
아래 ROUTER_MODULES에 한 줄 더한다. 자세한 규칙은 docs/W05_common_structure.md
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import db
from app.core.config import get_settings
from app.core.request_log import RequestLogMiddleware
from app.core.responses import CamelCaseMiddleware, install_error_handlers

import importlib

# 붙일 기능 목록 (기능 이름, 라우터 모듈). 그 브랜치에 아직 없는 기능은 건너뛴다 → 금요일에 하나씩 합쳐도 main.py를 고치지 않음
ROUTER_MODULES = [
    ("AUTH", "app.api.auth_api"),             # /api/auth  로그인·권한 (은경, I-01)
    ("AI-05", "app.api.ai05_law_api"),        # /api/ai05  법령 근거 (은경)
    ("AI-07", "app.api.ai07_explain_api"),    # /api/ai07  근거 설명문 (진이)
    ("AI-10", "app.api.ai10_review_api"),     # /api/ai10  조치 제안 검토 (대환)
    # 새 기능은 여기에 한 줄: ("AI-03", "app.api.ai03_xxx_api"), ("ENGINE", "app.api.engine_xxx_api") …
]


def _load_routers():
    loaded = []
    for name, module in ROUTER_MODULES:
        try:
            loaded.append((name, importlib.import_module(module).router))
        except ModuleNotFoundError as e:
            if e.name and module.startswith(e.name):     # 그 기능 파일이 아직 없는 브랜치 → 건너뜀
                continue
            raise                                         # 기능 안에서 패키지가 빠진 경우는 숨기지 않고 알림
    return loaded


ROUTERS = _load_routers()

app = FastAPI(
    title="RADAR 2.0",
    description="RADAR 2.0 공통 서버 — 기능별 API는 /api/<기능>/ 아래에 있습니다.",
    version="0.1.0",
)

settings = get_settings()
# 미들웨어는 아래에서 위 순서로 감싼다: 요청 로그 → camelCase → CORS(가장 바깥)
app.add_middleware(CamelCaseMiddleware)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,                 # 기본: 프론트 개발 서버 5173
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Response-Case"],
    expose_headers=["X-Request-ID"],
)
install_error_handlers(app)

for _name, _router in ROUTERS:
    app.include_router(_router)


@app.get("/")
def root():
    return {"service": "RADAR 2.0", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    """서버가 떠 있는지만 본다 (DB는 연결하지 않음)."""
    return {"status": "ok", "modules": [name for name, _ in ROUTERS], "db_configured": db.is_configured()}


@app.get("/health/db")
def health_db():
    """공용 DB에 실제로 붙는지 확인 (SELECT 1). 실패 이유는 내보내지 않는다."""
    if not db.is_configured():
        return {"status": "not_configured"}
    return {"status": "ok" if db.ping() else "unreachable"}
