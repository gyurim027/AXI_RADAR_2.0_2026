"""운영 API (I-05 대시보드 · I-06 실행 기록 · I-03 실패 알림). 주소: /api/ops/... · RADAR 운영자만.

GET  /api/ops/dashboard?days=30          실행 성공·실패·경고·실행 중 수, 안 읽은 알림 수, 업로드 수, 오늘 접근 기록 수
GET  /api/ops/runs?days=30&status=실패    실행 기록 목록 (status: 성공·실패·경고·실행 중·건너뜀, 비우면 전체)
GET  /api/ops/runs/{id}                   실행 한 건 + 단계 기록(logs)
GET  /api/ops/notifications?unread=true   실패 알림 목록 (화면 목업 listAdminNotifications의 failure 줄 모양)
POST /api/ops/notifications/{id}/read     알림 확인 (71 acknowledged_at·acknowledged_by)

화면 목업의 데이터 갱신(staleData)·법령 개정(regulation)·승인(approval) 알림은 각 기능이 생기면 여기에 더한다.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.auth import require_roles
from app.core.job_run import STATUSES, KINDS
from app.core.responses import ApiError
from app.services.ops.repository import OpsRepository, get_repository

router = APIRouter(prefix="/api/ops", tags=["운영 (I-03·05·06)"])
operator = require_roles("operator")


def _fmt(dt: datetime | None, with_time: bool = True) -> str | None:
    if not dt:
        return None
    return dt.strftime("%Y.%m.%d %H:%M" if with_time else "%Y.%m.%d")


def _run_row(r: dict) -> dict:
    return {"id": r["job_run_id"], "name": r["job_name"], "kind": r["job_kind"], "module": r.get("module"),
            "status": r["status"], "at": r["started_at"].isoformat(timespec="seconds") if r.get("started_at") else None,
            "at_label": _fmt(r.get("started_at")), "finished_at": _fmt(r.get("finished_at")),
            "minutes": r.get("minutes"), "row_cnt": r.get("row_cnt"), "error_code": r.get("error_code"),
            "cause": r.get("cause"), "ref_table": r.get("ref_table"), "ref_id": r.get("ref_id")}


@router.get("/dashboard")
def dashboard(days: int = Query(30, ge=1, le=366), _u: dict = Depends(operator),
              repo: OpsRepository = Depends(get_repository)):
    c = repo.run_counts(days)
    up = repo.upload_summary(days)
    return {
        "runs": {"days": days, "success": c.get("성공", 0), "failure": c.get("실패", 0), "warning": c.get("경고", 0),
                 "running": c.get("실행 중", 0), "skipped": c.get("건너뜀", 0)},
        "alerts": {"unread": repo.unread_alerts()},
        "uploads": {"days": days, "count": up["count"], "last_at": _fmt(up["last_at"])},
        "access": {"today": repo.access_today()},
    }


@router.get("/runs")
def runs(days: int = Query(30, ge=1, le=366), status: str | None = None, kind: str | None = None,
         limit: int = Query(200, ge=1, le=1000), _u: dict = Depends(operator),
         repo: OpsRepository = Depends(get_repository)):
    if status in (None, "", "전체"):
        status = None
    elif status not in STATUSES:
        raise ApiError(400, "invalid_status", "상태는 " + " · ".join(STATUSES) + " 중 하나입니다")
    if kind in (None, "", "전체"):
        kind = None
    elif kind not in KINDS:
        raise ApiError(400, "invalid_kind", "종류는 " + " · ".join(KINDS) + " 중 하나입니다")
    return {"runs": [_run_row(r) for r in repo.list_runs(days, status, kind, limit)]}


@router.get("/runs/{run_id}")
def run_detail(run_id: int, _u: dict = Depends(operator), repo: OpsRepository = Depends(get_repository)):
    r = repo.get_run(run_id)
    if not r:
        raise ApiError(404, "run_not_found", "실행 기록을 찾을 수 없습니다")
    row = _run_row(r)
    row["logs"] = [f"[{l['logged_at'].strftime('%H:%M')}] {l['message']}" if l.get("logged_at") else l["message"]
                   for l in r.get("logs", [])]
    return row


@router.get("/notifications")
def notifications(unread: bool = False, limit: int = Query(100, ge=1, le=500), _u: dict = Depends(operator),
                  repo: OpsRepository = Depends(get_repository)):
    rows = repo.list_alerts(unread, limit)
    return {"notifications": [
        {"id": a["alert_delivery_id"], "kind": "failure", "run_id": a["job_run_id"],
         "date": _fmt(a.get("sent_at"), with_time=False), "text": a.get("message"),
         "read": a.get("acknowledged_at") is not None} for a in rows]}


@router.post("/notifications/{alert_id}/read")
def read_notification(alert_id: int, user: dict = Depends(operator), repo: OpsRepository = Depends(get_repository)):
    if not repo.acknowledge(alert_id, user["user_id"]):
        raise ApiError(404, "notification_not_found", "알림을 찾을 수 없습니다")
    return {"ok": True}
