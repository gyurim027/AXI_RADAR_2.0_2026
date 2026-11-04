"""Fail-closed join of existing 77/78 result, evidence and current 62 snapshot.
No approval mutation and no production writer. Official results remain disabled.
"""
import math
from fastapi import APIRouter,Depends
from app.core import db
from app.core.auth import current_user,allowed_gus
from app.core.responses import ApiError

class ContractMismatch(ValueError):pass

def join_result(run,candidate,evidence,setting,manifest):
 def require(ok,reason):
  if not ok:raise ContractMismatch(reason)
 require(type(run.get('run_id')) is int,'RUN_ID_TYPE')
 require(run['run_id']==candidate.get('run_id')==evidence.get('run_id'),'RUN_ID_MISMATCH')
 require(candidate.get('gid')==evidence.get('gid'),'GRID_ID_MISMATCH')
 require(candidate.get('gu')==evidence.get('gu'),'GU_MISMATCH')
 require(run.get('rule_version')==evidence.get('rule_version'),'RUN_RULE_MISMATCH')
 require(bool(manifest.get('build_id')) and run.get('build_id')==manifest['build_id'],'BUILD_ID_MISMATCH')
 snap=evidence['setting_snapshot']
 for key in ['setting_version_id','setting_kind','version_label','content_ref','approval_status','approved_by','approved_at']:
  require(setting.get(key)==snap.get(key),'SETTING_CHANGED:'+key)
 require(setting['setting_version_id']==evidence['setting_version_id'],'SETTING_ID_MISMATCH')
 require(manifest.get('input_sha256')==evidence.get('input_sha256')==snap.get('input_sha256'),'INPUT_SNAPSHOT_MISMATCH')
 policy=next((p for p in manifest.get('policies',[]) if p.get('label')==setting.get('version_label')),None)
 require(policy is not None and policy==snap.get('policy'),'POLICY_CONTENT_MISMATCH')
 require(candidate.get('complaint_cnt')==evidence['details'].get('raw_complaint_count'),'COMPLAINT_COUNT_MISMATCH')
 require(candidate.get('complaint_cnt_excl_low')==evidence['details'].get('count_excl_low'),'LOW_COUNT_MISMATCH')
 require(evidence.get('official_score') is None,'OFFICIAL_NOT_IMPLEMENTED')
 state=evidence.get('calculation_status');require(state in ['EXPERIMENTAL','UNSCORED'],'UNVERIFIED_STATE')
 if state=='EXPERIMENTAL':
  a,b=candidate.get('score'),evidence.get('experimental_score')
  require(a is not None and b is not None and math.isfinite(float(a)) and math.isfinite(float(b)) and 0<=float(b)<=100 and abs(float(a)-float(b))<.000051,'SCORE_MISMATCH')
  require(candidate.get('rank_no')==evidence.get('experimental_rank'),'RANK_MISMATCH')
 else:
  require(candidate.get('score') is None and candidate.get('rank_no') is None and evidence.get('experimental_score') is None and evidence.get('experimental_rank') is None,'UNSCORED_HAS_VALUE')
 require(candidate.get('selected_yn') is None,'SELECTION_NOT_VERIFIED')
 return {'run_id':run['run_id'],'gid':candidate['gid'],'gu':candidate['gu'],'calculation_status':state,'official_score':None,'experimental_score':evidence.get('experimental_score'),'experimental_rank':evidence.get('experimental_rank'),'selected_yn':None,'setting_version_id':setting['setting_version_id'],'setting_status':setting['approval_status'],'rule_version':run['rule_version'],'details':evidence['details'],'integration_status':'VERIFIED_ISOLATED_JOIN','production_ready':False}

def create_router(store,manifest_loader):
 router=APIRouter(prefix='/api/engine-result',tags=['산정 결과 결합 (검토용)'])
 @router.get('/runs/{run_id}/candidates/{gid}')
 def result(run_id:int,gid:str,user:dict=Depends(current_user)):
  runs=db.read_only('SELECT * FROM priority_run WHERE run_id=%s',(run_id,))
  rows=db.read_only("SELECT c.*, NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '') AS gu FROM priority_candidate c LEFT JOIN grid_feature f ON f.ID_gid=c.gid WHERE c.run_id=%s AND c.gid=%s",(run_id,gid))
  if not runs or not rows:raise ApiError(404,'result_not_found','해당 회차·격자 결과가 없습니다')
  row=rows[0]
  if user.get('role')=='district' and row.get('gu') not in allowed_gus(user):raise ApiError(403,'forbidden_gu','담당 구가 아닌 자료입니다')
  ev=store.read(run_id,gid)
  settings=db.read_only('SELECT * FROM setting_version WHERE setting_version_id=%s',(ev['setting_version_id'],))
  if not settings:raise ApiError(409,'setting_missing','연결된 설정판본을 찾을 수 없습니다')
  try:return join_result(runs[0],row,ev,settings[0],manifest_loader(run_id))
  except (ContractMismatch, ValueError, OSError) as error:raise ApiError(409,'result_contract_mismatch',str(error)) from None
 return router
