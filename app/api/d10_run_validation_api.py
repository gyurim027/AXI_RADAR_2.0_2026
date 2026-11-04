
"""D-10 회차 생성 입력 검증 API. DB 쓰기 없음."""
from __future__ import annotations

from datetime import date
from importlib import import_module

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import require_roles
from app.core.responses import ApiError

_d10 = import_module(
    "app.services.d10.d10_run_create"
)

router = APIRouter(
    prefix="/api/d10",
    tags=["D-10 회차 입력 검증 (읽기 전용)"],
)

operator = require_roles("operator")


class RunValidationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    run_id: int = Field(..., gt=0)
    build_id: str = Field(..., min_length=1, max_length=30)
    rule_version: str = Field(..., min_length=1, max_length=128)

    period_start: date | None = None
    period_end: date | None = None

    note: str | None = Field(
        default=None,
        max_length=300,
    )


@router.post("/runs/validate")
def validate_run(
    payload: RunValidationRequest,
    _user: dict = Depends(operator),
):
    """회차 입력값만 검증한다. DB 저장은 수행하지 않는다."""
    try:
        row = _d10.validate_run_input(
            _d10.RunCreateInput(**payload.model_dump())
        )
    except _d10.D10RunError as exc:
        raise ApiError(
            422,
            "invalid_run_input",
            str(exc),
        ) from exc

    return {
        "ok": True,
        "valid": True,
        "input": {
            **row,
            "period_start": (
                row["period_start"].isoformat()
                if row["period_start"] is not None
                else None
            ),
            "period_end": (
                row["period_end"].isoformat()
                if row["period_end"] is not None
                else None
            ),
        },
        "created": False,
        "db_written": False,
        "checks_not_performed": [
            "run_id 사전 발급 여부",
            "DB 중복 회차",
            "산정 완료",
            "회차 상태",
        ],
        "note": (
            "입력값만 검증했습니다. "
            "회차 생성·열기 및 DB 저장은 수행하지 않았습니다."
        ),
    }
