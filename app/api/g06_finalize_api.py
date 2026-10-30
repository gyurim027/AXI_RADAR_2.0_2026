"""G-06 development-only district/round finalization API.

Reads the same process-local G-03 decisions; no persistent finalization.
Do not enable in production or regard round_finalized as a DB state.
"""
from __future__ import annotations

import os
from importlib import import_module
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import current_user
from app.services.priority.repository import PriorityRepository, get_repository

_g06 = import_module("app.services.G-01~06.g06_round_finalize")
_g03_api = import_module("app.api.g03_decision_api")
_store = _g06.InMemoryFinalizeStore()
_lock = RLock()
router = APIRouter(prefix="/api/g06", tags=["G-06 개발용 구별 확정"])


class ConfirmBody(BaseModel):
    explicitly_confirmed: bool
    reconfirm_undecided: bool = False


def _guard() -> None:
    if os.getenv("AI_G06_DEV_API_ENABLED") != "1":
        raise HTTPException(403, "G-06 개발용 확정 API 비활성화")
    if os.getenv("AI_G03_DEV_API_ENABLED") != "1":
        raise HTTPException(503, "G-03 결정 저장 기능이 비활성화돼 있습니다")


def _gu(user: dict) -> str:
    gu = user.get("gu")
    if user.get("role") != "district" or gu not in _g06.DISTRICTS:
        raise HTTPException(403, "본인 구 도로관리팀만 확정할 수 있습니다")
    return gu


def _candidates(repo: PriorityRepository, run_id: int, gu: str) -> list[dict]:
    if run_id <= 0:
        raise HTTPException(422, "유효한 회차 번호가 필요합니다")
    if repo.get_run(run_id) is None:
        raise HTTPException(404, "회차가 없습니다")
    # Existing frontend summary counts only scored candidates.
    result: list[dict] = []
    offset = 0
    while True:
        rows, total = repo.list_candidates(run_id, [gu], False, None, 500, offset)
        result.extend({"run_id": run_id, "gid": x["gid"], "gu": gu} for x in rows if x.get("score") is not None)
        offset += len(rows)
        if offset >= total or not rows:
            break
    if not result:
        raise HTTPException(409, "해당 구에 산정된 후보가 없습니다")
    return result


def _decisions(run_id: int, gu: str, gids: set[str]) -> list[dict]:
    return [d for d in _g03_api._store.list_for_run(run_id)
            if d.get("gu") == gu and d.get("gid") in gids]


@router.get("/runs/{run_id}/districts/me/confirmation")
def preview_confirmation(run_id: int, user: dict = Depends(current_user),
                         repo: PriorityRepository = Depends(get_repository)):
    _guard()
    gu = _gu(user)
    candidates = _candidates(repo, run_id, gu)
    with _g03_api._lock, _lock:
        saved = _store.get(run_id, gu)
        if saved:
            return {"role": "district", "gu": gu, "counts": {
                "target": saved["selected_count"], "exclude": saved["excluded_count"],
                "hold": saved["held_count"], "none": saved["undecided_count"]},
                "summary": saved, "mine": {"gu": gu, "done": True, "date": None},
                "storage": "development_memory_only", "operational_saved": False}
        try:
            summary = _g06.preview_district_finalization(
                run_id=run_id, gu=gu, candidates=candidates,
                decisions=_decisions(run_id, gu, {c["gid"] for c in candidates}), store=_store)
        except _g06.G06Error as exc:
            raise HTTPException(409, str(exc)) from exc
    return {"role": "district", "gu": gu, "counts": {
        "target": summary["selected_count"], "exclude": summary["excluded_count"],
        "hold": summary["held_count"], "none": summary["undecided_count"]},
        "summary": summary, "mine": {"gu": gu, "done": False, "date": None},
        "storage": "development_memory_only", "operational_saved": False}


@router.post("/runs/{run_id}/districts/me/confirmation", status_code=201)
def confirm_district(run_id: int, body: ConfirmBody, user: dict = Depends(current_user),
                     repo: PriorityRepository = Depends(get_repository)):
    _guard()
    gu = _gu(user)
    candidates = _candidates(repo, run_id, gu)
    uid = user.get("user_id")
    if type(uid) is not int or uid < 1:
        raise HTTPException(403, "인증 사용자 식별값이 필요합니다")
    with _g03_api._lock, _lock:
        try:
            result = _g06.finalize_district(
                run_id=run_id, gu=gu, candidates=candidates,
                decisions=_decisions(run_id, gu, {c["gid"] for c in candidates}),
                actor_role="구 도로관리팀", actor_gu=gu, actor_ref=str(uid),
                explicitly_confirmed=body.explicitly_confirmed,
                reconfirm_undecided=body.reconfirm_undecided, store=_store)
        except _g06.G06Error as exc:
            raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "result": result, "storage": "development_memory_only", "operational_saved": False}


@router.get("/runs/{run_id}/confirmation-status")
def confirmation_status(run_id: int, user: dict = Depends(current_user),
                        repo: PriorityRepository = Depends(get_repository)):
    _guard()
    if repo.get_run(run_id) is None:
        raise HTTPException(404, "회차가 없습니다")
    if user.get("role") not in {"city", "operator", "district"}:
        raise HTTPException(403, "조회 권한이 없습니다")
    with _lock:
        statuses = _store.list_run(run_id)
        items = [{"gu": gu, "done": record is not None} for gu, record in sorted(statuses.items())]
        if user["role"] == "district":
            items = [x for x in items if x["gu"] == user.get("gu")]
        return {"run_id": run_id, "guStatuses": items,
                "round_finalized": _store.round_finalized(run_id),
                "storage": "development_memory_only", "operational_saved": False}
