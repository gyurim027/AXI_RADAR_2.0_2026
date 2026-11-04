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
    ("ACCOUNTS", "app.api.accounts_api"),     # /api/admin 계정 관리·접속 기록 조회 (은경, I-01·I-04)
    ("OPS", "app.api.ops_api"),               # /api/ops   운영: 대시보드·실행 기록·실패 알림 (은경, I-03·05·06)
    ("PRIORITY", "app.api.priority_api"),     # /api/priority  우선순위 결과 조회 77·78·82 (은경, 계산은 진규)
    ("ALERT-MAIL", "app.api.alert_settings_api"),  # /api/admin/alert-email 실패 알림 메일 설정 (은경, I-03)
    ("AI-05", "app.api.ai05_law_api"),        # /api/ai05  법령 근거 (은경)
    ("APPROVALS", "app.api.approvals_api"),    # /api/approvals I-07 (진규)
    ("SETTINGS", "app.api.settings_api"),      # /api/settings/versions I-02 조회 (진규)
    ("SETTING-PROPOSALS", "app.api.setting_proposals_api"),  # /api/settings/proposals I-02 제안 (진규)
    ("INPUT-BUILDS", "app.api.input_builds_api"),  # DB59 입력 판본·원천감사 승인, 회차/산정 자동 실행 없음
    ("STANDARDS", "app.api.standards_api"),   # /api/standards  법령·업무 기준: A-11·A-12·F-05 (은경)
    ("AI-07", "app.api.ai07_explain_api"),    # /api/ai07  근거 설명문 (진이)
    ("DATA-ISSUES", "app.api.data_issues_api"),  # /api/data-issues A-05/A-06/A-08 통합 조회 (진이)
    ("AI-10", "app.api.ai10_review_api"),     # /api/ai10  조치 제안 검토 (대환)
    ("C-09", "app.api.c09_upload_api"),       # /api/c09   민원 파일 등록 (규림, W07-01)
    ("C-08", "app.api.c08_review_api"),       # /api/c08   분류 검수 (규림)
    ("AI-03", "app.api.ai03_location_api"),   # /api/ai03  좌표 결과 조회: 낮음 민원 목록 (세은, A-07·C-06)
    ("G-03", "app.api.g03_decision_api"),     # /api/g03   후보 결정 저장·조회 (대환)
    ("G-06", "app.api.g06_finalize_api"),     # /api/g06   구별·회차 확정 (대환)
    ("D-10-READ", "app.api.d10_run_read_api"),  # 대환 D-10 기존 API 유지
    ("D-10-VALIDATE", "app.api.d10_run_validation_api"),  # 대환 D-10 기존 API 유지
    ("D-10", "app.api.d10_operational_api"),  # 운영자 권한 회차 생성
    ("H-01", "app.api.h01_preview_api"),      # /api/h01   점검 요청서 미리보기 (진이) (feat(h01): add inspection request preview API)
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
