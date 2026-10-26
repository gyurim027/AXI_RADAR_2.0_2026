"""Extra read-only APIs for H-02/D-08/H-03; no schema changes or invented workflow data."""
from __future__ import annotations
from decimal import Decimal
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from app.core.auth import current_user, allowed_gus, check_gu
from app.core.responses import ApiError
from app.core import db

router = APIRouter(prefix="/api/priority", tags=["우선순위 회차조건·변동비교"])
_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"

def _safe(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v

def _run(run_id):
    rows = db.read_only('SELECT run_id,build_id,rule_version,created_at,note FROM priority_run WHERE run_id=%s',(run_id,))
    if not rows:
        raise ApiError(404,'run_not_found','회차가 없습니다')
    return {k:_safe(v) for k,v in rows[0].items()}

def _scope(user, gu):
    if gu:
        check_gu(user,gu)
        return [gu]
    if user.get('role')=='district':
        return allowed_gus(user)
    return None

@router.get('/runs/{run_id}/conditions')
def run_conditions(run_id:int, user:dict=Depends(current_user)):
    row=_run(run_id)
    # Neither setting ID nor period are columns of 77. Do not infer them from run label.
    return {**row,'setting_version_id':None,'setting_content_ref':None,
            'period_start':None,'period_end':None,
            'contract_status':'77_SCHEMA_HAS_NO_SETTING_OR_PERIOD_COLUMN'}

@router.get('/runs/{from_run_id}/compare/{to_run_id}')
def compare_runs(from_run_id:int,to_run_id:int, gu:str|None=None,
                 limit:int=Query(500,ge=1,le=3000),offset:int=Query(0,ge=0),
                 user:dict=Depends(current_user)):
    before=_run(from_run_id);after=_run(to_run_id)
    scope=_scope(user,gu)
    args=[from_run_id,to_run_id]
    where=''
    if scope is not None:
        if not scope:
            return {'from_run':before,'to_run':after,'total':0,'comparisons':[]}
        where=f' AND {_GU} IN ('+','.join(['%s']*len(scope))+')'
        args+=scope
    # UNION gid population: includes entries added in the second run, unlike left-join only.
    gids='(SELECT gid FROM priority_candidate WHERE run_id=%s UNION SELECT gid FROM priority_candidate WHERE run_id=%s) u'
    base=(f'FROM {gids} '
          'LEFT JOIN priority_candidate a ON a.gid=u.gid AND a.run_id=%s '
          'LEFT JOIN priority_candidate b ON b.gid=u.gid AND b.run_id=%s '
          'LEFT JOIN grid_feature f ON f.ID_gid=u.gid WHERE 1=1'+where)
    bind=[from_run_id,to_run_id,from_run_id,to_run_id,*args[2:]]
    count=db.read_only('SELECT COUNT(*) AS n '+base,bind)
    fields=(f'SELECT u.gid,{_GU} AS gu,a.score AS from_score,b.score AS to_score,'
            'a.rank_no AS from_rank,b.rank_no AS to_rank,'
            'a.selected_yn AS from_selected,b.selected_yn AS to_selected,'
            'CASE WHEN a.score IS NULL OR b.score IS NULL THEN NULL ELSE b.score-a.score END AS score_delta,'
            'CASE WHEN a.rank_no IS NULL OR b.rank_no IS NULL THEN NULL ELSE a.rank_no-b.rank_no END AS rank_improvement,'
            'CASE WHEN a.gid IS NULL THEN 0 ELSE 1 END AS present_in_from,'
            'CASE WHEN b.gid IS NULL THEN 0 ELSE 1 END AS present_in_to ')
    rows=db.read_only(fields+base+' ORDER BY u.gid LIMIT %s OFFSET %s',[*bind,limit,offset])
    return {'from_run':before,'to_run':after,'total':int(count[0]['n']) if count else 0,
            'limit':limit,'offset':offset,
            'comparisons':[{k:_safe(v) for k,v in r.items()} for r in rows],
            'interpretation':'STORED_SCORE_DIFFERENCE_NOT_CAUSAL_IMPROVEMENT',
            'period_policy':'NOT_RECORDED_IN_77'}


@router.get('/runs/{run_id}/trust-summary')
def trust_summary(run_id:int, user:dict=Depends(current_user)):
    """D-06: quantify persisted evidence availability and trust grades; never infer missing grade."""
    _run(run_id)
    scope=_scope(user,None)
    bind=[run_id]
    clause=''
    if scope is not None:
        if not scope:
            return {'run_id':run_id,'visible_candidates':0,'stored_evidence':0,'grades':{}}
        clause=f' AND {_GU} IN ('+','.join(['%s']*len(scope))+')'
        bind+=scope
    rows=db.read_only('SELECT c.gid,c.note FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid=c.gid '
                      'WHERE c.run_id=%s'+clause+' ORDER BY c.gid',bind)
    from app.services.priority.details import read_evidence
    grades={};stored=0
    for record in rows:
        if not str(record.get('note') or '').startswith('ev1:'):
            continue
        detail=read_evidence(db.read_only,run_id,record['gid'])
        if detail.get('stored'):
            stored+=1
            grade=detail.get('confidence_grade')
            grades[grade]=grades.get(grade,0)+1
    return {'run_id':run_id,'visible_candidates':len(rows),'stored_evidence':stored,
            'missing_evidence':len(rows)-stored,'grades':grades,
            'explanation':'COUNT_OF_RECORDED_GRADES_NOT_AN_INDEPENDENT_VALIDATION'}
