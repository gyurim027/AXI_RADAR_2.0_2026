from copy import deepcopy
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT=Path(__file__).resolve().parents[1]
client=TestClient(app,base_url='http://127.0.0.1:8000')

def load(name):return json.loads((ROOT/'samples'/name).read_text(encoding='utf-8'))

def test_base_health_and_routes_registered():
    assert 'AI-07' in client.get('/health').json()['modules']
    assert client.get('/api/ai07/health').status_code==200
    assert '/api/ai07/synthetic/report' in client.get('/openapi.json').json()['paths']

def test_explanation_preserves_number_and_camelcase():
    r=client.post('/api/ai07/synthetic/explanation',json=load('cards.json')[0]['card'])
    assert r.status_code==200
    assert '65.0000점' in r.json()['explanation']
    assert r.json()['externalApiCalled'] is False

def test_bad_refinement_returns_original():
    card=load('cards.json')[0]['card']
    original=client.post('/api/ai07/synthetic/explanation',json=card).json()['explanation']
    r=client.post('/api/ai07/synthetic/refine',json={'card':card,'proposed_text':original.replace('65.0000점','99.0000점')})
    assert r.status_code==200
    assert r.json()['refinementStatus']=='fallback'
    assert r.json()['explanation']==original

def test_request_and_unconfirmed_department():
    data=load('request.json');r=client.post('/api/ai07/synthetic/request',json=data)
    assert r.status_code==200 and r.json()['automaticSend'] is False
    assert r.json()['status']=='draft'
    data['department']['status']='unknown'
    assert client.post('/api/ai07/synthetic/request',json=data).status_code==400

def test_report_and_district_scope():
    data=load('report.json');r=client.post('/api/ai07/synthetic/report',json=data)
    assert r.status_code==200
    assert len(r.json()['sections'])==5
    data['scope']={'role':'district','district':'수정구'}
    r=client.post('/api/ai07/synthetic/report',json=data)
    assert 'SYNTHETIC-GRID-2' not in r.json()['reportText']
    assert '중원구' not in r.json()['reportText']

def test_unknown_actual_and_malformed_inputs():
    data=load('report.json');data['data_kind']='actual'
    assert client.post('/api/ai07/synthetic/report',json=data).status_code==400
    for payload in ({},{'card':{}},{'card':None}):
        assert client.post('/api/ai07/synthetic/refine',json=payload).status_code==400
    assert client.post('/api/ai07/synthetic/explanation',json=[]).status_code==422

def test_parent_local_host_restriction_is_inherited():
    other=TestClient(app,base_url='http://example.invalid')
    assert other.post('/api/ai07/synthetic/report',json=load('report.json')).status_code==403

def test_body_limit_and_error_detail_not_returned():
    r=client.post('/api/ai07/synthetic/report',json={'marker':'SENSITIVE_MARKER'+'x'*1048576})
    assert r.status_code==413 and 'SENSITIVE_MARKER' not in r.text
