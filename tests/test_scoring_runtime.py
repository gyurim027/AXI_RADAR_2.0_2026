import json,sqlite3
from pathlib import Path
import pandas as pd
import pytest
from app.services.scoring.runtime import execute,read_result
from app.services.scoring.calculation import FEATURES

@pytest.fixture
def setup(tmp_path):
    f=pd.DataFrame([{**dict.fromkeys(FEATURES,1),'ID_gid':g,'id_gu':'성남시 분당구','ext_survey_scope_obstacle':'Y'} for g in ['A','B']])
    f.to_csv(tmp_path/'grid.csv',index=False)
    pd.DataFrame({'gid':['A','B'],'complaint_all':[1,2],'complaint_lowexcluded':[1,2],'complaint_illustrative_filter':[1,2]}).to_csv(tmp_path/'complaints.csv',index=False)
    cfg={'schema_version':1,'run_id':1,'build_id':'test','setting_version_id':1,'policy':{'label':'experiment','normalization':'positive_upper','observation':'scope_aware','domain_weights':dict.fromkeys(['accident','hazard','exposure','vulnerability'],.25),'accident_reduce':'mean','missing':'renormalize'},'complaint_mode':'independent','coefficient_points':5,'fit_population':'all_input_positive_counts','comparison_population':'hazard_observed','input_status':'EXPLORATORY_PROXY','period_note':'synthetic test'}
    (tmp_path/'config.json').write_text(json.dumps(cfg))
    return [tmp_path/'grid.csv',tmp_path/'complaints.csv',tmp_path/'config.json',tmp_path/'db.sqlite']

def test_independent_math_and_retry(setup):
    execute(*setup)
    a=read_result(setup[3],1,'A');b=read_result(setup[3],1,'B')
    assert a['experimental_score']==97.5 and b['experimental_score']==100
    assert execute(*setup)['execution']=='REUSED'
    cfg=json.loads(setup[2].read_text());cfg['coefficient_points']=10;setup[2].write_text(json.dumps(cfg))
    with pytest.raises(ValueError,match='RUN_CONFLICT'):execute(*setup)
    assert read_result(setup[3],1,'A')['experimental_score']==97.5

def test_rollback_retry(setup):
    with pytest.raises(RuntimeError):execute(*setup,fail_after=1)
    with sqlite3.connect(setup[3]) as c:
        for t in ['priority_run','priority_candidate','evidence','setting_version']:assert c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]==0
    assert execute(*setup)['execution']=='COMMITTED'

def test_invalid_input(setup):
    f=pd.read_csv(setup[1]);f.loc[0,'complaint_all']=-1;f.to_csv(setup[1],index=False)
    with pytest.raises(ValueError,match='COUNT'):execute(*setup)
    assert not setup[3].exists()

def test_tamper(setup):
    execute(*setup)
    with sqlite3.connect(setup[3]) as c:c.execute('UPDATE priority_candidate SET complaint_cnt=999 WHERE gid="A"')
    with pytest.raises(ValueError,match='COUNT_MISMATCH'):read_result(setup[3],1,'A')

def test_http_auth_and_status(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.services.scoring.api import create_router
    from app.core.auth import current_user
    from app.core.responses import CamelCaseMiddleware,install_error_handlers
    execute(*setup);app=FastAPI();app.add_middleware(CamelCaseMiddleware);install_error_handlers(app);app.include_router(create_router(setup[3]));client=TestClient(app)
    assert client.get('/api/scoring-result/runs/1/candidates/A').status_code==401
    app.dependency_overrides[current_user]=lambda:{'role':'city'}
    response=client.get('/api/scoring-result/runs/1/candidates/A')
    assert response.status_code==200 and response.json()['experimentalScore']==97.5
    app.dependency_overrides[current_user]=lambda:{'role':'district','gu':'수정구'}
    assert client.get('/api/scoring-result/runs/1/candidates/A').status_code==403

def test_concurrent_same_run(setup):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:execute(*setup),range(2)))
    assert sorted(x['execution'] for x in results)==['COMMITTED','REUSED']
    with sqlite3.connect(setup[3]) as c:assert c.execute('SELECT COUNT(*) FROM priority_candidate').fetchone()[0]==2

def test_unobserved_and_approval_change(setup):
    f=pd.read_csv(setup[0]);f.loc[0,['cond_blind_spot_cnt','cond_pothole_detect_cnt','cond_delineator_detect_cnt']]=0;f.loc[0,'ext_survey_scope_obstacle']='N';f.to_csv(setup[0],index=False)
    execute(*setup);a=read_result(setup[3],1,'A')
    assert a['calculation_status']=='UNSCORED' and a['experimental_score'] is None and a['details']['complaint_signal_points'] is None
    with sqlite3.connect(setup[3]) as c:c.execute("UPDATE setting_version SET approval_status='승인'")
    with pytest.raises(ValueError,match='SETTING_CHANGED'):read_result(setup[3],1,'A')
