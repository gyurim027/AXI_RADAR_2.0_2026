"""우선순위 결과 조회 API (77·78·82, SQL v2.1). 주소: /api/priority/... · 로그인한 사람 모두 (구 도로관리팀은 자기 구만).

GET /api/priority/runs                                  실행 회차 목록 (최근 순) + 회차별 격자 수·뽑힌 수·점수 있는 수
GET /api/priority/runs/{run_id}/candidates?gu=&selected=Y&limit=&offset=
                                                        그 회차의 격자별 결과 (순위 순, 순위 없는 격자는 뒤)
GET /api/priority/runs/{run_id}/candidates/{gid}        격자 한 칸 결과 + 82 조치 제안

지키는 것
- 읽기만 한다. 점수·순위·후보 선정은 진규 산정 기능이 77·78에 쓴다.
- NULL은 NULL 그대로 내려보낸다. 점수가 없으면 score_status='미산출' (0점으로 바꾸지 않음).
- 78 상세 5칸(분야별 점수·지표별 기여·미평가 사유·신뢰도·사고 제외 점수)은 아직 DB에 없다 (진규 추가안, v2.2 예정).
  그 전까지는 details.stored=false 와 모두 null로 내려보낸다.
- run_id는 숫자 (77 priority_run.run_id BIGINT). 글자면 422.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.core.auth import allowed_gus, check_gu, current_user
from app.core.responses import ApiError
from app.services.priority.repository import PriorityRepository, get_repository

router = APIRouter(prefix="/api/priority", tags=["우선순위 결과 조회 (77·78·82)"])

DETAIL_NAMES = ("domain_scores", "indicator_contributions", "unevaluated_reasons", "confidence_grade",
                "score_excluding_accidents")


def _iso(v):
    return v.isoformat(timespec="seconds") if isinstance(v, datetime) else v


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _cnt(v):
    return int(v) if v is not None else 0


def _run(r: dict) -> dict:
    out = {"run_id": r["run_id"], "build_id": r.get("build_id"), "rule_version": r.get("rule_version"),
           "created_at": _iso(r.get("created_at")), "note": r.get("note")}
    if "candidate_cnt" in r:
        out.update(candidate_cnt=_cnt(r["candidate_cnt"]), selected_cnt=_cnt(r.get("selected_cnt")),
                   scored_cnt=_cnt(r.get("scored_cnt")))
    return out


def _candidate(c: dict) -> dict:
    score = _num(c.get("score"))
    return {
        "run_id": c["run_id"], "gid": c["gid"], "gu": c.get("gu"),
        "selected_yn": c.get("selected_yn"), "score": score, "rank_no": c.get("rank_no"),
        "score_status": "산출" if score is not None else "미산출",
        "complaint_cnt": c.get("complaint_cnt"), "complaint_cnt_excl_low": c.get("complaint_cnt_excl_low"),
        "conditions": {"result": c.get("cond_result_yn"), "hazard": c.get("cond_hazard_yn"),
                       "exposure": c.get("cond_exposure_yn"), "vulnerable": c.get("cond_vulnerable_yn")},
        "matched_roles": c.get("matched_roles"), "note": c.get("note"),
        "details": {"stored": False, **{k: None for k in DETAIL_NAMES}},
    }


def _scope(user: dict, gu: str | None) -> tuple[list[str] | None, bool]:
    """(볼 구 목록, 구 없는 격자 포함 여부). 구 도로관리팀은 자기 구만, 구 없는 격자는 못 봄."""
    if gu:
        check_gu(user, gu)
        return [gu], False
    if user.get("role") == "district":
        return allowed_gus(user), False
    return None, True


@router.get("/runs")
def runs(limit: int = Query(50, ge=1, le=500), _u: dict = Depends(current_user),
         repo: PriorityRepository = Depends(get_repository)):
    return {"runs": [_run(r) for r in repo.list_runs(limit)]}


@router.get("/runs/{run_id}/candidates")
def candidates(run_id: int, gu: str | None = None, selected: str | None = Query(None, pattern="^[YN]$"),
               limit: int = Query(500, ge=1, le=3000), offset: int = Query(0, ge=0),
               user: dict = Depends(current_user), repo: PriorityRepository = Depends(get_repository)):
    run = repo.get_run(run_id)
    if not run:
        raise ApiError(404, "run_not_found", "실행 회차를 찾을 수 없습니다")
    gus, include_no_gu = _scope(user, gu or None)
    rows, total = repo.list_candidates(run_id, gus, include_no_gu, selected, limit, offset)
    return {"run": _run(run), "total": total, "limit": limit, "offset": offset,
            "candidates": [_candidate(c) for c in rows]}


@router.get("/runs/{run_id}/candidates/{gid}")
def candidate(run_id: int, gid: str, user: dict = Depends(current_user),
              repo: PriorityRepository = Depends(get_repository)):
    c = repo.get_candidate(run_id, gid)
    if not c:
        raise ApiError(404, "candidate_not_found", "그 회차에 이 격자 결과가 없습니다")
    if user.get("role") == "district" and c.get("gu") not in allowed_gus(user):
        raise ApiError(403, "forbidden_gu", "담당 구가 아닌 자료입니다")
    out = _candidate(c)
    out["actions"] = [{k: _iso(a.get(k)) for k in ("item_id", "action_text", "dept_text", "basis_text", "created_at")}
                      for a in c.get("actions", [])]
    return out
