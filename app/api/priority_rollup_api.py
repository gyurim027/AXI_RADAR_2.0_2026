"""B11: read-only stored-run summary; no fictional half-year timestamps or action outcomes."""
from __future__ import annotations
from decimal import Decimal
from fastapi import APIRouter, Depends
from app.core.auth import current_user, allowed_gus
from app.core import db
from app.core.responses import ApiError

router = APIRouter(prefix='/api/priority', tags=['B11 회차 요약'])
_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"

def _number(value):
    if isinstance(value, Decimal): return float(value)
    return value

@router.get('/runs/{run_id}/rollup')
def rollup(run_id:int,user:dict=Depends(current_user)):
    runs=db.read_only('SELECT run_id, build_id, rule_version, created_at FROM priority_run WHERE run_id=%s',(run_id,))
    if not runs: raise ApiError(404,'run_not_found','회차가 없습니다')
    scope=allowed_gus(user) if user.get('role')=='district' else None
    where=' WHERE c.run_id=%s'
    args=[run_id]
    if scope is not None:
        if not scope:
            return {'run_id':run_id,'visible_candidates':0,'selected_count':0,'scored_count':0,'unscored_count':0,'score_mean':None,'period_verified':False,'halfyear_verified':False,'action_effectiveness':None}
        where+=f' AND {_GU} IN ('+','.join(['%s']*len(scope))+')'
        args.extend(scope)
    sql=("SELECT COUNT(*) AS visible_candidates, "
         "COALESCE(SUM(CASE WHEN c.selected_yn='Y' THEN 1 ELSE 0 END),0) AS selected_count, "
         "COALESCE(SUM(CASE WHEN c.score IS NOT NULL THEN 1 ELSE 0 END),0) AS scored_count, "
         "AVG(c.score) AS score_mean "
         "FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid=c.gid"+where)
    row=db.read_only(sql,args)[0]
    total=int(row['visible_candidates']); scored=int(row['scored_count'])
    return {'run_id':run_id,'build_id':runs[0]['build_id'],'rule_version':runs[0]['rule_version'],
            'visible_candidates':total,'selected_count':int(row['selected_count']),
            'scored_count':scored,'unscored_count':total-scored,
            'score_mean':_number(row['score_mean']),
            'period_verified':False,'halfyear_verified':False,'action_effectiveness':None,
            'note':'Stored run counts only; not verified semiannual renewal or measured safety improvement'}
