"""우선순위 결과 조회 API (77·78·82, SQL v2.1). 주소: /api/priority/... · 로그인한 사람 모두 (구 도로관리팀은 자기 구만).

GET /api/priority/runs                                  실행 회차 목록 (최근 순) + 회차별 격자 수·뽑힌 수·점수 있는 수
GET /api/priority/runs/{run_id}/candidates?gu=&selected=Y&limit=&offset=
                                                        그 회차의 격자별 결과 (순위 순, 순위 없는 격자는 뒤)
GET /api/priority/runs/{run_id}/candidates/{gid}        격자 한 칸 결과 + 82 조치 제안

지키는 것
- 읽기만 한다. 점수·순위·후보 선정은 진규 산정 기능이 77·78에 쓴다.
- NULL은 NULL 그대로 내려보낸다. 점수가 없으면 score_status='미산출' (0점으로 바꾸지 않음).
- 78 상세 8개 항목은 DB 컬럼에서 읽는다. 없는 값은 NULL을 보존한다.
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
                "score_excluding_accidents", "exclusion_reasons", "complaint_contribution", "policy_version")


def _iso(v):
    return v.isoformat(timespec="seconds") if isinstance(v, datetime) else v


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _cnt(v):
    return int(v) if v is not None else 0


def _run(r: dict) -> dict:
    out = {"run_id": r["run_id"], "build_id": r.get("build_id"), "rule_version": r.get("rule_version"),
           "created_at": _iso(r.get("created_at")), "note": r.get("note"),
           "period_start": str(r["period_start"]) if r.get("period_start") is not None else None,
           "period_end": str(r["period_end"]) if r.get("period_end") is not None else None}
    out.update({k:r.get(k) for k in (
        'weight_setting_version_id','threshold_setting_version_id',
        'priority_condition_setting_version_id','setting_versions',
        'setting_version_display','setting_links_status')})
    if "candidate_cnt" in r:
        out.update(candidate_cnt=_cnt(r["candidate_cnt"]), selected_cnt=_cnt(r.get("selected_cnt")),
                   scored_cnt=_cnt(r.get("scored_cnt")))
    return out


def _candidate(c: dict) -> dict:
    score = _num(c.get("score"))
    return {
        "run_id": c["run_id"], "gid": c["gid"], "gu": c.get("gu"),
        "center_lat": _num(c.get("center_lat")), "center_lon": _num(c.get("center_lon")),
        "selected_yn": c.get("selected_yn"), "score": score, "rank_no": c.get("rank_no"),
        "score_status": "산출" if score is not None else "미산출",
        "complaint_cnt": c.get("complaint_cnt"), "complaint_cnt_excl_low": c.get("complaint_cnt_excl_low"),
        "conditions": {"result": c.get("cond_result_yn"), "hazard": c.get("cond_hazard_yn"),
                       "exposure": c.get("cond_exposure_yn"), "vulnerable": c.get("cond_vulnerable_yn")},
        "matched_roles": c.get("matched_roles"), "note": None if isinstance(c.get("note"), str) and c["note"].startswith("ev1:") else c.get("note"),
        "details": c.get("details") if c.get("details") is not None else {"stored": False, **{k: None for k in DETAIL_NAMES}},
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
    run = repo.get_run(run_id)
    if not run:
        raise ApiError(409, 'run_missing', '결과의 실행회차를 확인할 수 없습니다')
    out = _candidate(c)
    out['run'] = _run(run)
    from app.services.ai07.read_only_db import stored_explanation
    try:
        summary = stored_explanation({**c, 'rule_version': run.get('rule_version')})
    except ValueError:
        raise ApiError(409, 'invalid_stored_result', '저장된 점수·순위를 확인할 수 없습니다') from None
    out['explanation_context'] = {'run_id': run_id, 'gid': gid,
        'source': 'STORED_DB_RESULT', 'generation_method': 'local_template',
        'external_api_called': False, 'summary': summary,
        'score_status': out['score_status'], 'details': out['details'],
        'complaint_count_is_not_contribution': True, 'official_policy_verified': False}
    out["actions"] = [{k: _iso(a.get(k)) for k in ("item_id", "action_text", "dept_text", "basis_text", "created_at")}
                      for a in c.get("actions", [])]
    return out


# B07_READ_ONLY_LINEAGE_ROUTE_V1
@router.get("/runs/{run_id}/lineage")
def run_lineage(run_id: int, user: dict = Depends(current_user)):
    if user.get("role") == "district":
        raise ApiError(403, "forbidden_gu", "? ???? ?? ?? ??? ??? ? ????")
    from app.services.priority.lineage import read_run_lineage
    result = read_run_lineage(run_id)
    if result is None:
        raise ApiError(404, "run_not_found", "실행 회차를 찾을 수 없습니다")
    return result

@router.get("/runs/{run_id}/evidence")
def run_evidence(run_id: int, gu: str | None = None,
                 selected: str | None = Query(None, pattern="^[YN]$"),
                 limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 user: dict = Depends(current_user), repo: PriorityRepository = Depends(get_repository)):
    """Eight DB78 fields for an authorized page; no ev1 pointer or filesystem dependency.
    """
    run = repo.get_run(run_id)
    if not run:
        raise ApiError(404, "run_not_found", "실행 회차를 찾을 수 없습니다")
    gus, include_no_gu = _scope(user, gu or None)
    rows, total = repo.list_candidates(run_id, gus, include_no_gu, selected, limit, offset)
    from app.core import db
    from app.services.priority.details import read_evidence
    results = []
    stored = 0
    missing = 0
    errors = 0
    for row in rows:
        item = {"run_id": run_id, "gid": row["gid"], "gu": row.get("gu"),
                "score": _num(row.get("score")), "rank_no": row.get("rank_no")}
        try:
            details = read_evidence(db.read_only, run_id, row["gid"])
            if details.get('complete'):
                item.update(evidence_status='STORED_DB78', details=details)
                stored += 1
            elif details.get('stored'):
                item.update(evidence_status='PARTIAL_DB78', details=details)
                missing += 1
            else:
                item.update(evidence_status='UNSTORED', details=details)
                missing += 1
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            item.update(evidence_status='INTEGRITY_ERROR', details=None,
                        evidence_error=type(exc).__name__)
            errors += 1
        results.append(item)
    return {"run": _run(run), "total": total, "limit": limit, "offset": offset,
            "stored_verified": stored, "storage": "DB78", "verification_basis": "DB_VALUE_VALIDATION", "unstored": missing, "integrity_errors": errors,
            "official_policy_verified": False, "candidates": results}

@router.get('/runs/{run_id}/actions')
def b09_candidate_actions(run_id: int, gu: str | None = None,
                          selected: str | None = Query(None, pattern='^[YN]$'),
                          action_filter: str = Query('all', pattern='^(all|with_action|without_action)$'),
                          limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                          user: dict = Depends(current_user),
                          repo: PriorityRepository = Depends(get_repository)):
    """B09: stored 77/78 candidates and actual 82 rows, no synthetic actions.

    item_id/action_text/dept_text/basis_text/created_at are the only verified
    columns from 82; don't invent workflow states or an assigned operator.
    """
    from app.core import db
    run = repo.get_run(run_id)
    if not run:
        raise ApiError(404, 'run_not_found', '실행 회차를 찾을 수 없습니다')
    gus, include_no_gu = _scope(user, gu or None)
    if gus is not None and not gus:
        return {'run': _run(run), 'total': 0, 'limit': limit, 'offset': offset,
                'candidates': [], 'source': '77_78_82_STORED_DB',
                'action_status_basis': '82_RECORD_PRESENCE_ONLY'}
    args = [run_id]
    where = ['c.run_id = %s']
    if gus is not None:
        where.append("NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '') IN (" + ','.join(['%s'] * len(gus)) + ')')
        args += list(gus)
    elif not include_no_gu:
        where.append("NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '') IS NOT NULL")
    if selected:
        where.append('c.selected_yn = %s')
        args.append(selected)
    action_exists = ('EXISTS (SELECT 1 FROM priority_candidate_action a '
                     'WHERE a.run_id = c.run_id AND a.gid = c.gid)')
    if action_filter == 'with_action':
        where.append(action_exists)
    elif action_filter == 'without_action':
        where.append('NOT ' + action_exists)
    base = (' FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid = c.gid '
            'WHERE ' + ' AND '.join(where))
    count = db.read_only('SELECT COUNT(*) AS n' + base, args)
    rows = db.read_only(
        "SELECT c.run_id, c.gid, c.selected_yn, c.score, c.rank_no, "
        "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '') AS gu, "
        "(SELECT COUNT(*) FROM priority_candidate_action a "
        " WHERE a.run_id=c.run_id AND a.gid=c.gid) AS action_count"
        + base + ' ORDER BY c.rank_no IS NULL, c.rank_no, c.gid LIMIT %s OFFSET %s',
        [*args, limit, offset])
    gids = [r['gid'] for r in rows]
    grouped = {gid: [] for gid in gids}
    if gids:
        binds = ','.join(['%s'] * len(gids))
        action_rows = db.read_only(
            'SELECT run_id,gid,item_id,action_text,dept_text,basis_text,created_at '
            'FROM priority_candidate_action WHERE run_id=%s AND gid IN (' + binds + ') '
            'ORDER BY gid,item_id', [run_id, *gids])
        for action in action_rows:
            gid = action['gid']
            if gid in grouped:
                grouped[gid].append({
                    'item_id': action.get('item_id'),
                    'action_text': action.get('action_text'),
                    'dept_text': action.get('dept_text'),
                    'basis_text': action.get('basis_text'),
                    'created_at': _iso(action.get('created_at'))})
    results = []
    for c in rows:
        actual = grouped[c['gid']]
        results.append({
            'run_id': c['run_id'], 'gid': c['gid'], 'gu': c.get('gu'),
            'selected_yn': c.get('selected_yn'), 'score': _num(c.get('score')),
            'rank_no': c.get('rank_no'),
            'action_status': 'RECORDED_ACTION' if actual else 'NO_RECORDED_ACTION',
            'action_count': len(actual), 'actions': actual,
            'workflow_status': None, 'assignee': None})
    return {'run': _run(run), 'total': int(count[0]['n']) if count else 0,
            'limit': limit, 'offset': offset, 'candidates': results,
            'source': '77_78_82_STORED_DB',
            'action_status_basis': '82_RECORD_PRESENCE_ONLY',
            'note': '82 기록 존재 여부만 판정하며, 미기록은 실제 미조치의 증명이 아닙니다.'}

@router.get('/runs/{run_id}/decision-basis')
def b10_decision_basis(run_id: int, gu: str | None = None,
                       selected: str | None = Query(None, pattern='^[YN]$'),
                       limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
                       user: dict = Depends(current_user),
                       repo: PriorityRepository = Depends(get_repository)):
    """B10 D-05 / D-06: expose *stored* decision flags separately from evidence reliability.

    A stored selected_yn is not evidence that the thresholds were validated;
    confidence_grade is not derivable from score. No policy guessed here.
    """
    from app.services.priority.details import read_evidence
    from app.core import db
    run = repo.get_run(run_id)
    if not run:
        raise ApiError(404, 'run_not_found', '실행 회차를 찾을 수 없습니다')
    gus, include_no_gu = _scope(user, gu or None)
    rows, total = repo.list_candidates(run_id, gus, include_no_gu, selected, limit, offset)
    output = []
    for row in rows:
        gid = row['gid']
        status = 'UNSTORED'
        details = None
        try:
            evidence = read_evidence(db.read_only, run_id, gid)
            if evidence.get('stored'):
                status = 'STORED_DB78' if evidence.get('complete') else 'PARTIAL_DB78'
                details = evidence
        except (ValueError, FileNotFoundError, RuntimeError, OSError, KeyError, TypeError) as exc:
            status = 'INTEGRITY_OR_STORAGE_ERROR'
        selected_value = row.get('selected_yn')
        flags = {k: row.get(k) for k in
                 ('cond_result_yn', 'cond_hazard_yn', 'cond_exposure_yn', 'cond_vulnerable_yn')}
        output.append({
            'run_id': run_id, 'gid': gid, 'gu': row.get('gu'),
            'D05': {
                'selected_yn': selected_value,
                'score': _num(row.get('score')),
                'rank_no': row.get('rank_no'),
                'stored_conditions': flags,
                'matched_roles': row.get('matched_roles'),
                'source': '78_STORED_RESULT',
                'policy_conditions_verified': False,
                'decision_status': 'NOT_RECORDED' if selected_value is None else 'STORED_NOT_REVALIDATED',
            },
            'D06': {
                'evidence_status': status,
                'confidence_grade': details.get('confidence_grade') if details else None,
                'unevaluated_reasons': details.get('unevaluated_reasons') if details else None,
                'source': '78_STORED_DETAIL_COLUMNS' if details else None,
                'independent_from_score': True,
            },
        })
    return {
        'run': _run(run), 'total': total, 'limit': limit, 'offset': offset,
        'items': output, 'read_only': True,
        'policy_conditions_verified': False,
        'note': 'Stored result inspection only; no retroactive approval or inferred confidence.'
    }
