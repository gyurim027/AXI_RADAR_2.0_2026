"""Opt-in, isolated evidence endpoint. No production writes, approvals or action creation.
Existing /api/priority endpoints are unchanged. A team-agreed durable store is still required.
"""
import hashlib,json,sqlite3
from pathlib import Path
from fastapi import APIRouter,Depends
from app.core.auth import current_user,allowed_gus
from app.core.responses import ApiError

def canonical(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def digest(text):return hashlib.sha256(text.encode()).hexdigest()

class EvidenceStore:
 def __init__(self,path):self.path=Path(path).resolve()
 def read(self,run_id,gid):
  with sqlite3.connect('file:'+str(self.path)+'?mode=ro',uri=True) as con:
   row=con.execute('SELECT payload,sha256 FROM evidence WHERE run_id=? AND gid=?',(run_id,gid)).fetchone()
   if not row:raise ApiError(404,'evidence_not_found','해당 회차·격자 근거가 없습니다')
   if digest(row[0])!=row[1]:raise ApiError(409,'evidence_integrity','근거 무결성을 확인할 수 없습니다')
   obj=json.loads(row[0]);setting=con.execute('SELECT payload,sha256 FROM setting_snapshot WHERE setting_version_id=?',(obj['setting_version_id'],)).fetchone()
   if not setting or digest(setting[0])!=setting[1] or obj['setting_sha256']!=setting[1]:raise ApiError(409,'setting_mismatch','설정판본 연결이 맞지 않습니다')
   if obj['run_id']!=run_id or obj['gid']!=gid:raise ApiError(409,'identity_mismatch','근거 식별자가 맞지 않습니다')
   if obj['calculation_status'] not in ['EXPERIMENTAL','UNSCORED'] or obj['official_score'] is not None:raise ApiError(409,'unverified_official_result','공식 결과로 검증되지 않았습니다')
   obj['setting_snapshot']=json.loads(setting[0]);return obj

def create_router(store):
 router=APIRouter(prefix='/api/engine-evidence',tags=['산정 근거 (검증용)'])
 @router.get('/runs/{run_id}/candidates/{gid}')
 def evidence(run_id:int,gid:str,user:dict=Depends(current_user)):
  # Authorization is resolved before exposing integrity/setting details.
  with sqlite3.connect('file:'+str(store.path)+'?mode=ro',uri=True) as con:
   row=con.execute('SELECT gu FROM evidence WHERE run_id=? AND gid=?',(run_id,gid)).fetchone()
  if not row:raise ApiError(404,'evidence_not_found','해당 회차·격자 근거가 없습니다')
  if user.get('role')=='district' and row[0] not in allowed_gus(user):raise ApiError(403,'forbidden_gu','담당 구가 아닌 자료입니다')
  obj=store.read(run_id,gid)
  if obj.get('gu')!=row[0]:raise ApiError(409,'scope_mismatch','근거 관할 정보가 맞지 않습니다')
  return obj
 return router
