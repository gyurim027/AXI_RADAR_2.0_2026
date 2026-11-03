"""G-03 후보 결정 개발용 API.

주의: 저장은 프로세스 메모리 한정이며 운영 DB에 쓰지 않는다.
AI_G03_DEV_API_ENABLED=1일 때만 사용한다. 결정은 운영 DB에 저장하지 않는다.
공용 app/main.py 라우터 등록은 통합 담당자 영역이다.
"""
from __future__ import annotations

import os
from importlib import import_module
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import allowed_gus, current_user
from app.services.priority.repository import PriorityRepository, get_repository
from app.services.priority import g03_operational_store as _operational

_g03 = import_module("app.services.g01_g06.g03_candidate_decision")
_store = _g03.InMemoryDecisionStore()
_lock = RLock()

router = APIRouter(prefix="/api/g03", tags=["G-03 개발용 후보 결정"])


class CandidateDecisionBody(BaseModel):
    decision: str
    reason_code: str | None = None
    reason_text: str | None = Field(default=None, max_length=100)
    memo: str = Field(default="", max_length=200)


# 프론트의 copy.js reasonOptionsByDecision과 동일한 개발 계약.
# 향후 공식 사유 코드 정책이 결정되면 양쪽을 함께 변경해야 한다.
REASON_BY_DECISION = {
    "우선 점검 대상": set(),
    "제외": {"현장 확인 결과 문제 없음", "이미 정비 계획에 있음", "다른 부서 소관", "기타"},
    "보류": {"예산·공정 사정", "추가 확인 필요", "기타"},
}


def _guard() -> None:
    if os.getenv("AI_G03_DEV_API_ENABLED") != "1" and not _operational.enabled():
        raise HTTPException(403, "G-03 개발용 메모리 API 비활성화")


def _validate_reason(body: CandidateDecisionBody) -> set[str]:
    allowed = REASON_BY_DECISION.get(body.decision)
    if allowed is None:
        raise HTTPException(400, "지원하지 않는 결정입니다")
    if body.decision in {"제외", "보류"} and not body.reason_code:
        raise HTTPException(400, "제외·보류는 사유가 필요합니다")
    if body.reason_code is not None and body.reason_code not in allowed:
        raise HTTPException(400, "해당 결정에서 허용되지 않는 사유입니다")
    if body.reason_code == "기타":
        if not body.reason_text or not body.reason_text.strip():
            raise HTTPException(400, "기타 사유를 입력해야 합니다")
    elif body.reason_text is not None:
        raise HTTPException(400, "기타 선택이 아닐 때 기타 사유는 사용할 수 없습니다")
    return allowed


def _district(user: dict, candidate: dict) -> str:
    if user.get("role") != "district":
        raise HTTPException(403, "구 도로관리팀만 결정할 수 있습니다")
    gu = candidate.get("gu")
    if gu not in allowed_gus(user):
        raise HTTPException(403, "담당 구가 아닌 후보입니다")
    return gu


class _OneCandidateReader:
    def __init__(self, candidate: dict):
        self.candidate = candidate

    def find(self, run_id: int, gid: str) -> dict | None:
        if self.candidate.get("run_id") == run_id and self.candidate.get("gid") == gid:
            return self.candidate
        return None


@router.post("/runs/{run_id}/candidates/{gid}/decision", status_code=201)
def create_candidate_decision(
    run_id: int,
    gid: str,
    body: CandidateDecisionBody,
    user: dict = Depends(current_user),
    repo: PriorityRepository = Depends(get_repository),
):
    """개발용 최초 결정만 기록. 재결정은 G-04, 운영 DB 저장은 별도."""
    _guard()
    codes = _validate_reason(body)
    if run_id <= 1 or not gid.strip():
        raise HTTPException(422, "유효한 회차와 격자 번호가 필요합니다")
    candidate = repo.get_candidate(run_id, gid)
    if candidate is None:
        raise HTTPException(404, "해당 회차의 후보가 없습니다")
    gu = _district(user, candidate)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(404, "회차가 없습니다")
    # 실제 스키마에 확정된 회차 확정 상태가 없으므로, 운영 수준의 확인 불가.
    # 개발용 API에서 확정 여부를 추정하지 않는다.
    weight_version = run.get("rule_version")
    if not isinstance(weight_version, str) or not weight_version.strip():
        raise HTTPException(409, "회차 규칙 버전 미확인")
    uid = user.get("user_id")
    if type(uid) is not int or uid < 1:
        raise HTTPException(403, "인증 사용자 ID 미확인")
    if _operational.enabled():
        try:
            record = _operational.create_decision(
                run_id=run_id, gid=gid, gu=gu, decision=body.decision,
                reason_code=body.reason_code, reason_text=body.reason_text,
                memo=body.memo, actor_id=uid, rule_version=weight_version,
            )
        except _operational.OperationalError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        return {"ok": True, "record": record,
                "storage": "operational_db", "operational_saved": True}
    req = _g03.DecisionRequest(
        run_id=run_id, gid=gid, decision=body.decision,
        reason_code=body.reason_code, memo=body.memo,
        weight_version=weight_version, actor_ref=str(uid),
        actor_role="구 도로관리팀", actor_gu=gu,
        reason_text=body.reason_text,
    )
    # G-06 확정 메모리와 동일한 잠금을 사용한다. G-06도 G-03 → G-06 순서로 잠근다.
    # 운영 DB의 확정 상태를 의미하지는 않는다.
    _g06_api = import_module("app.api.g06_finalize_api")
    with _lock, _g06_api._lock:
        if _g06_api._store.round_finalized(run_id) or _g06_api._store.get(run_id, gu):
            raise HTTPException(409, "이미 확정된 구 또는 회차에는 결정을 추가할 수 없습니다")
        try:
            record = _g03.record_candidate_decision(
                request=req, candidate_reader=_OneCandidateReader(candidate),
                store=_store, allowed_reason_codes=codes,
                round_is_finalized=False,  # 개발용에 한해 사용; 운영 확정 여부 증명 아님
            )
        except _g03.G03Error as exc:
            msg = str(exc)
            raise HTTPException(409 if "기존 결정" in msg or "이미 기록" in msg else 400, msg) from exc
    return {"ok": True, "record": record, "storage": "development_memory_only", "operational_saved": False}


@router.get("/runs/{run_id}/candidates/{gid}/decision")
def get_candidate_decision(
    run_id: int,
    gid: str,
    user: dict = Depends(current_user),
    repo: PriorityRepository = Depends(get_repository),
):
    _guard()
    candidate = repo.get_candidate(run_id, gid)
    if candidate is None:
        raise HTTPException(404, "해당 회차의 후보가 없습니다")
    _district(user, candidate)
    if _operational.enabled():
        try:
            record = _operational.get_decision(
                run_id=run_id, gid=gid, gu=candidate.get("gu"))
        except _operational.OperationalError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        if record is None:
            raise HTTPException(404, "운영 DB 결정 기록이 없습니다")
        return {"record": record, "storage": "operational_db",
                "operational_saved": True}
    with _lock:
        record = _store.get(run_id, gid)
    if record is None:
        raise HTTPException(404, "개발용 결정 기록이 없습니다")
    return {"record": record, "storage": "development_memory_only", "operational_saved": False}


@router.get("/runs/{run_id}/decisions")
def list_run_decisions(
    run_id: int,
    user: dict = Depends(current_user),
):
    """Existing G-03 process-memory decisions (NOT operational DB decisions).

    The frontend excludes legacy run 1; the server keeps read-only access.
    District can only read its own district; city can read all three.
    """
    _guard()
    if run_id <= 0:
        raise HTTPException(422, "유효한 회차 번호가 필요합니다")
    role = user.get("role")
    if role not in {"district", "city"}:
        raise HTTPException(403, "구 도로관리팀·시 도로과만 조회할 수 있습니다")
    if role == "district":
        permitted = set(allowed_gus(user))
        if not permitted:
            raise HTTPException(403, "담당 구를 확인할 수 없습니다")
    else:
        permitted = {"수정구", "중원구", "분당구"}
    if _operational.enabled():
        try:
            return _operational.list_decisions(run_id=run_id, user=user)
        except _operational.OperationalError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
    with _lock:
        saved = _store.list_for_run(run_id)
    decisions = []
    for record in saved:
        if record.get("gu") not in permitted:
            continue
        value = record.get("decided_at")
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif value is not None and not isinstance(value, str):
            value = None
        reason = record.get("reason_code")
        result = {
            "gid": record["gid"],
            "decision": record.get("decision"),
            "reason_code": reason,
            "decided_at": value,
        }
        if reason == "기타":
            result["reason_text"] = record.get("reason_text")
        decisions.append(result)
    decisions.sort(key=lambda row: row["gid"])
    return {
        "run_id": run_id,
        "decisions": decisions,
        "storage": "development_memory_only",
        "operational_saved": False,
    }
