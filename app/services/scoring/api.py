"""Opt-in isolated router; reuse team auth and response middleware."""
from pathlib import Path
import sqlite3
from fastapi import APIRouter,Depends
from app.core.auth import current_user,allowed_gus
from app.core.responses import ApiError
from .runtime import read_result

def create_router(database):
    router=APIRouter(prefix='/api/scoring-result')
    @router.get('/runs/{run_id}/candidates/{gid}')
    def get_result(run_id:int,gid:str,user=Depends(current_user)):
        if user.get('role') not in ['city','operator','district']:raise ApiError(403,'forbidden','허용되지 않은 역할입니다')
        try:
            with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True) as c:
                scope=c.execute("SELECT NULLIF(REPLACE(f.id_gu,'성남시 ',''),'') FROM priority_candidate p JOIN grid_feature f ON f.ID_gid=p.gid WHERE p.run_id=? AND p.gid=?",(run_id,gid)).fetchone()
            if scope is None:raise ApiError(404,'missing','결과가 없습니다')
            if user['role']=='district' and scope[0] not in allowed_gus(user):raise ApiError(403,'forbidden_gu','담당 구가 아닙니다')
            return read_result(database,run_id,gid)
        except LookupError:raise ApiError(404,'missing','결과가 없습니다') from None
        except (ValueError,KeyError,TypeError):raise ApiError(409,'mismatch','산정 결과와 근거가 일치하지 않습니다') from None
        except sqlite3.Error:raise ApiError(503,'unavailable','산정 저장소를 조회할 수 없습니다') from None
    return router
