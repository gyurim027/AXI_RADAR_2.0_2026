"""C-08 분류 검수 API. 화면 회차 ID는 77 priority_run.run_id(숫자)."""
from __future__ import annotations

import csv
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.core import access_audit
from app.core.auth import GU_LIST, client_ip, require_roles
from app.core.responses import ApiError
from app.services.c08.policy import accuracy
from app.services.c08.repository import ADMIN, DISTRICT, C08Repository, get_repository

router = APIRouter(prefix="/api/c08", tags=["C-08 분류 검수"])


class ReviewInput(BaseModel):
    result: Literal["맞음", "고침"]
    relevance: Literal["관련", "비관련", "불명"] | None = None
    label: str | None = None


def _run(repo: C08Repository, run_id: int) -> dict:
    scope = repo.run_scope(run_id)
    if scope is None:
        raise ApiError(404, "run_not_found", "회차를 찾을 수 없습니다")
    if not scope.get("period_start") or not scope.get("period_end"):
        raise ApiError(503, "run_scope_missing", "회차의 민원 자료 기간이 아직 정해지지 않았습니다")
    return scope


def _gu(user: dict, gu: str | None) -> str | None:
    if gu and gu not in GU_LIST:
        raise ApiError(422, "invalid_gu", "구 이름이 맞지 않습니다")
    if user["role"] == "district":
        if user.get("gu") not in GU_LIST:
            raise ApiError(403, "forbidden_gu", "담당 구가 정해지지 않았습니다")
        if gu and gu != user["gu"]:
            raise ApiError(403, "forbidden_gu", "담당 구의 자료만 볼 수 있습니다")
        return user["gu"]
    return gu


def _item(row: dict, district: bool) -> dict:
    confidence = row.get("class_confidence")
    out = {"id": row["sample_id"], "gu": row["gu"],
           "summary": row["masked_summary"],
           "label": row.get("ped_type"), "keywords": row.get("class_reason"),
           "sample_group": row["sample_group"]}
    if district:
        out["done"] = ({"result": row["done_result"], "label": row.get("done_label")}
                       if row.get("done_result") else None)
    else:
        out.update(relevance="관련" if row.get("relevance") == "보행안전 관련" else row.get("relevance"),
                   confidence=round(float(confidence) * 100) if confidence is not None else None,
                   done=row.get("done_result"))
    return out


@router.get("/samples")
def samples(run_id: int = Query(..., alias="runId"), gu: str | None = None,
            upload_id: int | None = Query(None, alias="uploadId"),
            user: dict = Depends(require_roles("operator", "district")),
            repo: C08Repository = Depends(get_repository)):
    if upload_id is not None:
        raise ApiError(422, "upload_filter_removed", "이제 회차의 민원 접수 기간으로 조회합니다")
    scope = _run(repo, run_id)
    gu = _gu(user, gu)
    district = user["role"] == "district"
    types = repo.type_options()
    if district:
        repo.ensure_district_samples(run_id)
        rows = repo.samples(run_id, DISTRICT, gu)
    else:
        repo.ensure_admin_samples(run_id)
        rows = repo.samples(run_id, ADMIN, gu)
    return {"run": {"id": run_id, "period_start": scope["period_start"], "period_end": scope["period_end"]},
            "available": repo.has_complaints(run_id, gu), "relevance": ["관련", "비관련", "불명"] if not district else None,
            "types": types if not district else None, "labels": types if district else None,
            "items": [_item(row, district) for row in rows]}


@router.post("/samples/{sample_id}/review")
def review(sample_id: int, body: ReviewInput, request: Request,
           user: dict = Depends(require_roles("operator", "district")),
           repo: C08Repository = Depends(get_repository)):
    if user["role"] == "district" and "relevance" in body.model_fields_set:
        raise ApiError(403, "relevance_forbidden", "구 도로관리팀은 관련 여부를 고칠 수 없습니다")
    relevance = "보행안전 관련" if body.relevance == "관련" else body.relevance
    repo.review(sample_id, user, body.result, relevance, body.label, client_ip(request))
    return {"ok": True}


@router.get("/accuracy")
def accuracy_result(run_id: int = Query(..., alias="runId"),
                    upload_id: int | None = Query(None, alias="uploadId"),
                    _user: dict = Depends(require_roles("operator")),
                    repo: C08Repository = Depends(get_repository)):
    if upload_id is not None:
        raise ApiError(422, "upload_filter_removed", "이제 회차의 민원 접수 기간으로 조회합니다")
    _run(repo, run_id)
    repo.ensure_district_samples(run_id)        # 운영자 표본도 함께 고정한다
    return {"run_id": run_id, "relevance": accuracy(repo.accuracy_strata(run_id, ADMIN)),
            "type": accuracy(repo.accuracy_strata(run_id, DISTRICT))}


@router.get("/evaluation")
def evaluation(request: Request, run_id: int = Query(..., alias="runId"),
               target: Literal["relevance", "pedType"] = "relevance",
               user: dict = Depends(require_roles("operator")),
               repo: C08Repository = Depends(get_repository)):
    _run(repo, run_id)
    repo.ensure_district_samples(run_id)
    rows = repo.evaluation_rows(run_id, target)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("case_id", "입력", "기대 답", "맞음 기준", "메모"))
    for row in rows:
        expected = row["after_relevance"] if target == "relevance" else row["after_ped_type"]
        writer.writerow((f"C08-{row['sample_id']}", row["masked_summary"], expected, "같음",
                         f"{row['review_scope']} / {row['sample_group']}"))
    access_audit.record(request, user, access_audit.DOWNLOAD,
                        key=f"C-08 {run_id} {target} 평가 자료", reason="분류 평가")
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="c08_{run_id}_{target}.csv"'})
