"""B11 semiannual run timeline: actual stored run timestamps only."""
from datetime import datetime, date
from fastapi import APIRouter, Depends
from app.core.auth import current_user
from app.core import db

router = APIRouter(prefix='/api/priority', tags=['B11 반기 회차'])

def halfyear_key(dt):
    if not isinstance(dt,(datetime,date)):
        return None
    return f'{dt.year}-H{1 if dt.month <= 6 else 2}'

@router.get('/runs/halfyear-timeline')
def halfyear_timeline(user:dict=Depends(current_user)):
    rows=db.read_only('SELECT run_id, created_at, build_id, rule_version FROM priority_run ORDER BY created_at, run_id')
    result=[]
    for row in rows:
        key=halfyear_key(row.get('created_at'))
        result.append({'run_id':row['run_id'],'created_at':row.get('created_at'),
                       'halfyear_by_created_at':key,'build_id':row.get('build_id'),
                       'rule_version':row.get('rule_version'),
                       'source_period_verified':False,'semiannual_renewal_verified':False})
    return {'runs':result,'count':len(result),'source_period_verified':False,
            'semiannual_renewal_verified':False,
            'note':'created_at halfyear is calendar metadata only; it does not certify input coverage or refresh'}
