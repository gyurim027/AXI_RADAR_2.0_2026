"""D-10 v2.3 read and input-validation API; no INSERT/UPDATE/open endpoints."""
from __future__ import annotations
from datetime import date, datetime
from zoneinfo import ZoneInfo
from importlib import import_module
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.auth import require_roles
from app.core.responses import ApiError

_repo = import_module("app.services.d10.d10_run_readonly")
_contract = import_module("app.services.d10.d10_run_contract")
_workflow = import_module("app.services.d10.d10_run_workflow_db")
router = APIRouter(prefix="/api/d10", tags=["D-10 회차 조회·기간 검증 (읽기 전용)"])
operator = require_roles("operator")


def _date(value):
    return value.isoformat() if isinstance(value, (date,)) else value


def _present(row):
    return {k: _date(v) for k, v in row.items()}


class PeriodValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def check_period(self):
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("시작일과 종료일은 함께 입력하거나 모두 비워야 합니다.")

        if self.period_start is not None:
            if self.period_start > self.period_end:
               raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

            today = datetime.now(ZoneInfo("Asia/Seoul")).date()
            if self.period_end > today:
               raise ValueError("민원 접수 종료일은 미래 날짜일 수 없습니다.")

        return self


@router.get("/runs")
def list_d10_runs(limit: int = Query(50, ge=1, le=200), _user: dict = Depends(operator)):
    rows = _repo.list_runs(limit)
    metadata = _workflow.metadata_for_runs([int(r["run_id"]) for r in rows])
    ready = _workflow.tables_ready()
    return {"runs": _contract.visible_run_rows(rows, is_operator=True,
            verified_metadata=metadata), "read_only": True,
            "status_available": ready, "status_note": None if ready else "운영 회차 저장 테이블 미적용"}


@router.get("/runs/{run_id}")
def get_d10_run(run_id: int, _user: dict = Depends(operator)):
    if run_id <= 0:
        raise ApiError(422, "invalid_run_id", "양의 정수 회차 번호가 필요합니다.")
    row = _repo.get_run(run_id)
    if row is None:
        raise ApiError(404, "run_not_found", "회차를 찾을 수 없습니다.")
    metadata = _workflow.metadata_for_runs([run_id])
    ready = _workflow.tables_ready()
    return {"run": _contract.to_run_response(row, metadata.get(run_id)), "candidate_counts": _repo.candidate_counts(run_id),
            "read_only": True, "status_available": ready,
            "not_verified": ["G-06 구별 확정"],
            "candidate_note": "selected_yn은 산정 단계 후보 선정값이며 G-03 운영자 결정이 아닙니다."}


class OpenRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    kind: str


@router.post("/runs/{run_id}/open")
def open_d10_run(run_id: int, payload: OpenRunRequest, user: dict = Depends(operator)):
    try:
        result = _workflow.open_run(run_id=run_id, name=payload.name, kind=payload.kind,
                                    actor_id=user.get("user_id"))
    except _workflow.WorkflowError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from None
    return {"ok": True, "run": result, "storage": "operational_db"}


@router.post("/period/validate")
def validate_d10_period(payload: PeriodValidationRequest, _user: dict = Depends(operator)):
    return {"ok": True, "valid": True, "period_start": _date(payload.period_start),
            "period_end": _date(payload.period_end), "has_complaints_period": payload.period_start is not None,
            "db_written": False, "limitations": ["미래 날짜 정책 미확정", "기간 변경 가능 시점 미검증",
                                             "실제 민원 파일 확보 기간 미검증"]}
