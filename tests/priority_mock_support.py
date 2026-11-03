"""Actual RADAR functions + strict transactional Fake connections. No real DB.

Original policy/audit bytes are verified; ALL approval rows, candidates and DB77
rows here are synthetic test-only objects. They do not attest real DB approval.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import pytest
from app.services.scoring import setting_links as L
from app.services.scoring.policy_preflight import (
    preflight_policy, compare_components, store_policy_evidence, PolicyPreflightBlocked)
from app.services.scoring.source_audit_lineage import (
    verify_source_audit, revalidate_source_audit, store_source_audit, verify_run_binding,
    source_audit_note, SourceAuditBlocked)
from app.services.d10_run_creation import RunCreation, create_d10_run, D10RunBlocked, SETTING_FIELDS
from app.services.scoring.production_writer import OfficialBatch, plan, ProductionBlocked
from app.services.scoring.mysql_writer import write_approved_batch
from app.services.priority.db8_details import COLS, JSON_INDEXES
from app.services.scoring.official_pipeline import OfficialInputs, run_official_pipeline
from app.services.scoring.r02_full_source_quarantine import prepare_full_source_r02

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'_priority_next_execution/r01_hazard_policy_approved_20261101_033116_004891/integrated_policy_draft_hazard_missing_approved.json'
AUDIT=ROOT/'_priority_next_execution/r02_full_source_quarantine_20261101_012021/full_source_policy_audit.json'
POLICY_SHA='f28a608c2593750b44dce44ddb5f68128df229e7eb0b00082c963d0ac545da81'
AUDIT_SHA='abed6e98e083564e935a11d50f4142dc99ae5aa67823c5112c7c012fe85f857f'
START,END=date(2021,1,1),date(2026,9,30)

def receipt():return verify_source_audit(AUDIT.read_bytes(),expected_sha256=AUDIT_SHA,start=START,end=END,grid_count=2406)

def request():return RunCreation('MOCK_BUILD',json.loads(POLICY.read_bytes())['policy']['label'],START,END,2,3,4)


def rows():
    return [dict(setting_version_id=i,setting_kind=kind,content_ref='sha256:'+POLICY_SHA,
                 version_label=request().rule_version,version_no=None,
                 approval_status='APPROVED',approved_at='MOCK_ONLY_NOT_DB_APPROVAL')
            for i,kind in zip((2,3,4),L.KINDS)]

class FakeDB:
    def __init__(self,mode=None):
        self.runs={};self.candidates={};self.settings=rows();self.calls=[]
        self.mode=mode;self.connections=[];self.next_id=2;self.legacy_accesses=0
    def connect(self):
        c=FakeConnection(self);self.connections.append(c);return c
    def reader(self,sql,args=()):
        c=FakeConnection(self);cur=c.cursor();cur.execute(sql,args);return cur.fetchall()

class FakeConnection:
    def __init__(self,db):
        self.db=db;self.runs=deepcopy(db.runs);self.candidates=deepcopy(db.candidates)
        self.commits=0;self.rollbacks=0;self.closed=0
    def cursor(self):return FakeCursor(self)
    def commit(self):
        self.commits+=1;self.db.runs=deepcopy(self.runs);self.db.candidates=deepcopy(self.candidates)
        if self.runs:self.db.next_id=max(self.runs)+1
    def rollback(self):self.rollbacks+=1
    def close(self):self.closed+=1

class FakeCursor:
    def __init__(self,con):self.con=con;self.result=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def fetchall(self):return deepcopy(self.result)
    def execute(self,sql,args=()):
        c=self.con;db=c.db;mode=db.mode;db.calls.append((sql,args))
        if 'priority_run WHERE run_id=%s' in sql or 'priority_candidate WHERE run_id=%s' in sql:
            if args[0] == 1:
                db.legacy_accesses+=1;raise AssertionError('LEGACY_ROW_ACCESS')
        self.result=[]
        if sql.startswith('SELECT GET_LOCK'):self.result=[{'acquired':0 if mode=='lock_fail' else 1}]
        elif sql.startswith('SELECT RELEASE_LOCK'):self.result=[{'released':1}]
        elif "TABLE_NAME='priority_run' AND COLUMN_NAME='run_id'" in sql:self.result=[{'EXTRA':''}]
        elif "TABLE_NAME='priority_run'" in sql:
            cols={'run_id','build_id','rule_version','created_at','note','period_start','period_end',*SETTING_FIELDS}
            if mode=='missing_schema':cols.remove('weight_setting_version_id')
            self.result=[{'COLUMN_NAME':col} for col in cols]
        elif 'information_schema.COLUMNS' in sql:
            self.result=[{'name':col,'data_type':'json' if i in JSON_INDEXES else 'decimal' if i in (4,6) else 'varchar',
                          'nullable':'YES','column_type':'json' if i in JSON_INDEXES else 'decimal(18,6)' if i in (4,6) else 'varchar(40)' if i==3 else 'varchar(255)'} for i,col in enumerate(COLS)]
        elif 'FROM setting_version' in sql:
            self.result=[r for r in db.settings if r['setting_version_id'] in args]
        elif 'COALESCE(MAX(run_id)' in sql:
            assert 'WHERE run_id>1' in sql
            self.result=[{'next_id':db.next_id}]
        elif sql.startswith('INSERT INTO priority_run'):
            rid,build,rule,note,start,end,*ids=args
            if rid in c.runs:raise RuntimeError('DUPLICATE_MOCK_PRIMARY_KEY')
            c.runs[rid]={'run_id':rid,'build_id':build,'rule_version':rule,'note':note,'period_start':start,'period_end':end,**dict(zip(SETTING_FIELDS,ids))}
        elif 'FROM grid_feature' in sql:self.result=[{'ID_gid':args[0]}]
        elif 'FROM priority_run WHERE run_id=%s' in sql:
            self.result=[c.runs[args[0]]] if args[0] in c.runs else []
            if mode=='bad_run_readback' and self.result:self.result=[{**self.result[0],'note':'corrupt'}]
        elif sql.startswith('INSERT INTO priority_candidate'):
            if mode=='insert_fail':raise RuntimeError('INJECTED_MOCK_INSERT_FAILURE')
            columns=sql.partition('(')[2].partition(')')[0].split(',')
            row=dict(zip(columns,args));key=(row['run_id'],row['gid'])
            if key in c.candidates:raise RuntimeError('DUPLICATE_MOCK_CANDIDATE')
            c.candidates[key]=row
        elif sql.startswith('SELECT COUNT(*) AS n FROM priority_candidate'):
            self.result=[{'n':sum(k[0]==args[0] for k in c.candidates)}]
            if mode=='bad_count':self.result=[{'n':999}]
        elif sql.startswith('SELECT gid,'):
            self.result=[r for (rid,_),r in c.candidates.items() if rid==args[0]]
            if mode=='bad_detail' and self.result:self.result[0]={**self.result[0],'complaint_contribution':999}
        else:raise AssertionError('UNEXPECTED_MOCK_SQL:'+sql)


def batch_and_evidence(db,grids=2,source=AUDIT_SHA):
    refs=tuple(L._validated_row(r,k) for r,k in zip(db.settings,L.KINDS))
    cs=tuple(dict(gid=f'MOCK_{i}',official_score=50,rank_no=1,complaint_cnt=0,complaint_cnt_excl_low=0,
             selected_yn='N',calculation_status='OFFICIAL',input_status='VERIFIED_CLASSIFIED',classification_status='COMPLETE',
             cond_result_yn=None,cond_hazard_yn=None,cond_exposure_yn=None,cond_vulnerable_yn=None,matched_roles=None)
             for i in range(grids))
    ev={c['gid']:{'domain_scores':{'hazard':None,'exposure':0.5},'indicator_contributions':{'mock':50},
                 'unevaluated_reasons':['MOCK_ONLY'],'confidence_grade':'UNVERIFIED',
                 'score_excluding_accidents':50,'exclusion_reasons':[], 'complaint_contribution':0,
                 'policy_version':request().rule_version} for c in cs}
    b=OfficialBatch('MOCK_BUILD',request().rule_version,2,'sha256:'+POLICY_SHA,'a'*64,POLICY_SHA,'b'*64,
                    cs,'MOCK_OPERATOR','MOCK_APPROVAL',refs,START,END,source)
    return b,ev


def create(db,source=None):return create_d10_run(request(),explicit_creation_approval=True,connection_factory=db.connect,source_audit=source)

def write(db,rid=2):
    b,e=batch_and_evidence(db)
    return write_approved_batch(b,explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=db.connect,existing_run_id=rid)


