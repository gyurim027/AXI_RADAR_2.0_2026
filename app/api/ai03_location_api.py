"""AI-03 좌표 결과 조회 API (79 src_complaint ← 05 grid_feature, SQL v2.1). 주소: /api/ai03/...

GET /api/ai03/low-complaints?gu=&limit=&offset=   좌표 정확도 '낮음' 민원 목록 (화면 AD-04 낮음 민원·지도)

지키는 것
- 읽기만 한다. 좌표는 AI-03 좌표 반영 단계가 79에 쓴다 (빈 좌표 행만, dry-run 뒤 한 거래).
- 민원 점 위치라서 로그인이 필요하고, 구 도로관리팀은 자기 구만 본다. 구가 빈 격자의 민원은 시 도로과·RADAR 운영자만 본다.
- 볼 때마다 접근 기록(70 access_audit, 민원 점 위치)을 남긴다. 로그인 한 번 동안 구·업무 목적이 같으면 한 줄 (공통 구조 10장, POL-022).
- 정확도 '낮음'은 정확한 주소 좌표가 아니다. 장소 이름 검색·내부 자료 대조로 찾은 근처 건물 좌표(대부분), 민원 본문에서 뽑은 위치값, 지번 주소 일부가 섞여 있다.
  화면에는 '대략 위치'로 보여야 하고, 어떻게 찾았는지는 method_kind로 구분한다.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pymysql import MySQLError

from app.core import access_audit as audit
from app.core import db
from app.core.auth import GU_LIST, allowed_gus, check_gu, current_user
from app.core.responses import ApiError
from app.services.ai03.low_complaints import LowComplaintRepository, get_repository

router = APIRouter(prefix="/api/ai03", tags=["AI-03 좌표 결과 조회 (79)"])

REASON = "좌표 정확도 낮음 민원 확인"      # 접근 기록의 업무 목적


def _scope(user: dict, gu: str | None) -> tuple[list[str] | None, bool]:
    """(볼 구 목록, 구 없는 격자 포함 여부). 구 도로관리팀은 자기 구만, 구 없는 격자는 못 봄."""
    if gu:
        check_gu(user, gu)
        return [gu], False
    if user.get("role") == "district":
        return allowed_gus(user), False
    return None, True


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _day(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def _kind(method: str | None) -> str | None:
    """좌표를 어떻게 얻었는지 한 단어로 (화면 표시용).
    장소 이름 검색 → '장소' · 민원 본문의 위치값 → '본문 위치값' · 지번·도로명 주소 검색 → '주소' · 내부 자료 대조 → '내부 대조'."""
    m = method or ""
    if "장소" in m:
        return "장소"
    if "본문" in m:
        return "본문 위치값"
    if "내부 대조" in m:
        return "내부 대조"
    if "주소" in m:
        return "주소"
    return "기타" if m else None


def _row(r: dict) -> dict:
    return {"complaint_id": r["complaint_id"], "source_type": r.get("source_type"),
            "received_date": _day(r.get("received_date")), "location_text": r.get("location_text"),
            "gu": r.get("gu"), "admin_dong_name": r.get("admin_dong_name"), "gid": r.get("gid"),
            "lat": _num(r.get("lat")), "lon": _num(r.get("lon")), "coord_method": r.get("coord_method"),
            "coord_accuracy": r.get("coord_accuracy"), "method_kind": _kind(r.get("coord_method"))}


@router.get("/low-complaints")
def low_complaints(request: Request, gu: str | None = None, limit: int = Query(200, ge=1, le=1000),
                   offset: int = Query(0, ge=0), user: dict = Depends(current_user),
                   repo: LowComplaintRepository = Depends(get_repository)):
    gus, include_no_gu = _scope(user, gu or None)
    try:
        for g in (gus if gus is not None else list(GU_LIST)):      # 보는 구마다 접근 기록 (다른 구면 여기서도 403)
            audit.complaint_points(request, user, g, REASON)       # 기록이 안 되면 목록도 안 보여 준다
        rows, total = repo.list_low(gus, include_no_gu, limit, offset)
    except db.DbNotConfigured:
        raise ApiError(503, "db_not_configured", "서버 설정이 필요합니다.")                 # 12_오류 케이스 ERR-13
    except MySQLError:
        raise ApiError(503, "db_read_failed", "낮음 민원 목록을 불러오지 못했습니다.")      # ERR-11 (연결·쿼리 오류 내용은 안 내보낸다)
    return {"total": total, "limit": limit, "offset": offset, "complaints": [_row(r) for r in rows]}
