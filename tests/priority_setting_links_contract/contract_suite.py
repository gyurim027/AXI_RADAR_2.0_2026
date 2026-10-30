"""독립 합성 시험. 실제 app.core·DB·모델은 불러오지 않는다."""
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from dataclasses import replace
import ast
import copy
import hashlib
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
CODE_ROOT=Path(os.environ.get('RADAR_LINK_TEST_ROOT',str(HERE/'payload')))
for name,rel in [('app','app'),('app.services','app/services'),
                 ('app.services.scoring','app/services/scoring'),
                 ('app.services.priority','app/services/priority'),('app.core','app/core')]:
    module=types.ModuleType(name);module.__path__=[str(CODE_ROOT/rel)];sys.modules[name]=module
db=types.ModuleType('app.core.db')
def no_db(*a,**k):raise AssertionError('실제 DB 호출 금지')
db.read_only=no_db;db.raw_connection=no_db;sys.modules['app.core.db']=db
L=importlib.import_module('app.services.scoring.setting_links')
P=importlib.import_module('app.services.scoring.production_writer')
W=importlib.import_module('app.services.scoring.mysql_writer')
C=importlib.import_module('app.services.priority.db8_details')
R=importlib.import_module('app.services.priority.repository')

DOC={'policy':{'label':'TEST_ONLY','domain_weights':{'accident':.3,'hazard':.35,'exposure':.2,'vulnerability':.15},
     'normalization':'positive_mid','observation':'scope_aware','missing':'renormalize','accident_reduce':'mean'},
     'complaint_mode':'inside_hazard','complaint_strength':.15,'confidence_thresholds':{'high':8/9,'medium':6/9},
     'accident_exclusion':'reweight_observed_nonaccident','selection_min_score':70,
     'input_period_start':'2021-01-01','input_period_end':'2026-09-30',
     'd05_rule':{'TEST_ONLY_THRESHOLD':.7}}

def registry(directory,docs=None):
    rows=[];(directory/'policies').mkdir()
    for i,kind,number in zip((10,20,30),L.KINDS,(2,1,3)):
        doc=copy.deepcopy((docs or {}).get(kind,DOC));doc['policy']['label']='ROW_LABEL_'+str(i)
        raw=json.dumps(doc,ensure_ascii=False).encode();digest=hashlib.sha256(raw).hexdigest()
        (directory/'policies'/(digest+'.json')).write_bytes(raw)
        rows.append(dict(setting_version_id=i,setting_kind=kind,version_no=number,
                         content_ref='sha256:'+digest,version_label='ROW_LABEL_'+str(i),
                         approval_status='승인',approved_at=datetime(2026,10,30)))
    return rows

def refs():
    return tuple(L.SettingReference(i,k,'sha256:'+str(n)*64,'LABEL_'+str(i),v)
                 for i,k,n,v in zip((10,20,30),L.KINDS,(1,2,3),(2,1,3)))

def batch():
    return P.OfficialBatch(build_id='TEST_ONLY_BUILD',rule_version='TEST_ONLY_POLICY',setting_version_id=2,
        setting_content_ref='sha256:'+'a'*64,input_digest='b'*64,policy_digest='a'*64,
        complaint_contract_digest='c'*64,authorized_by='TEST_ONLY',approval_reference='TEST_ONLY',
        candidates=({'gid':'TEST_GRID','official_score':77.5,'rank_no':1,'complaint_cnt':4,'complaint_cnt_excl_low':3,
                     'selected_yn':'Y','calculation_status':'OFFICIAL','input_status':'VERIFIED_CLASSIFIED',
                     'classification_status':'COMPLETE','source_kind':'TEST_SYNTHETIC'},),
        setting_references=refs(),period_start=date(2021,1,1),period_end=date(2026,9,30))

def evidence():
    return {'TEST_GRID':dict(domain_scores={'hazard':50},indicator_contributions={'test':10},
        unevaluated_reasons={},confidence_grade='HIGH',score_excluding_accidents=69.5,
        exclusion_reasons=[],complaint_contribution=-1.5,policy_version='TEST_ONLY_POLICY')}

class Cursor:
    def __init__(self,connection):self.connection=connection;self.result=[];self.lastrowid=42
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def execute(self,sql,args=None):
        c=self.connection;c.calls.append((sql,args))
        if 'FROM setting_version WHERE setting_version_id IN' in sql:
            if c.mode=='missing_schema':raise RuntimeError('unknown version_no')
            self.result=[dict(setting_version_id=r.setting_version_id,setting_kind=r.setting_kind,
                content_ref=r.content_ref,version_label=r.version_label,version_no=r.version_no,
                approval_status='승인',approved_at=datetime(2026,10,30)) for r in refs()]
            if c.mode=='changed_ref':self.result[0]['content_ref']='sha256:'+'f'*64
        elif 'FROM setting_version WHERE setting_version_id=' in sql:
            self.result=[dict(setting_version_id=2,version_label='TEST_ONLY_POLICY',content_ref='sha256:'+'a'*64,
                approval_status='승인',approved_at=datetime(2026,10,30))]
        elif 'information_schema.COLUMNS' in sql:
            self.result=[dict(name=col,data_type='json' if i in C.JSON_INDEXES else 'decimal' if i in (4,6) else 'varchar',
                nullable='YES',column_type='json' if i in C.JSON_INDEXES else 'decimal(18,6)' if i in (4,6) else 'varchar(40)' if i==3 else 'varchar(255)') for i,col in enumerate(C.COLS)]
        elif 'FROM grid_feature' in sql:self.result=[{'ID_gid':'TEST_GRID'}]
        elif 'FROM priority_run WHERE note=' in sql:self.result=[]
        elif sql.startswith('INSERT INTO priority_run'):
            c.run={'period_start':args[3],'period_end':args[4],**dict(zip(L.FIELDS,args[5:]))};self.result=[]
        elif sql.startswith('INSERT INTO priority_candidate'):
            c.saved={'gid':args[1],**dict(zip(C.COLS,args[-8:]))};self.result=[]
        elif sql.startswith('SELECT COUNT(*) AS n FROM priority_candidate'):self.result=[{'n':1}]
        elif sql.startswith('SELECT gid,'):
            self.result=[dict(c.saved)]
            if c.mode=='bad_detail':self.result[0]['complaint_contribution']=Decimal('9')
        elif sql.startswith('SELECT period_start,period_end,'):
            self.result=[dict(c.run)]
            if c.mode=='bad_run':self.result[0][L.FIELDS[0]]=999
        else:raise AssertionError('미지정 SQL: '+sql)
    def fetchall(self):return self.result

class Connection:
    def __init__(self,mode=None):self.mode=mode;self.calls=[];self.committed=False;self.rolled=False;self.closed=False
    def cursor(self):return Cursor(self)
    def commit(self):self.committed=True
    def rollback(self):self.rolled=True
    def close(self):self.closed=True

class LinksTests(unittest.TestCase):
    def setUp(self):self.mode=patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'v24'});self.mode.start()
    def tearDown(self):self.mode.stop()
    def prepare(self,docs=None,edit=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);rows=registry(p,docs)
            if edit:edit(rows,p)
            return L.prepare_references(lambda sql,args:rows,(10,20,30),p,DOC)
    def test_ids_and_display_sequences_are_distinct(self):
        r=self.prepare();self.assertEqual([x.setting_version_id for x in r],[10,20,30]);self.assertEqual([x.version_no for x in r],[2,1,3])
    def test_weight_change_is_not_falsely_recorded(self):
        d=copy.deepcopy(DOC);d['policy']['domain_weights']['hazard']=.5
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_USED'):self.prepare({'가중치':d})
    def test_threshold_change_is_not_falsely_recorded(self):
        d=copy.deepcopy(DOC);d['selection_min_score']=80
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_USED'):self.prepare({'기준값':d})
    def test_condition_change_is_not_falsely_recorded(self):
        d=copy.deepcopy(DOC);d['d05_rule']={'TEST_ONLY_THRESHOLD':.8}
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_USED'):self.prepare({'우선 확인 조건':d})
    def test_wrong_kind_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'KIND_MISMATCH'):self.prepare(edit=lambda r,p:r[0].update(setting_kind='기준값'))
    def test_unapproved_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_APPROVED'):self.prepare(edit=lambda r,p:r[1].update(approval_status='제안'))
    def test_document_label_mismatch_is_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'LABEL_MISMATCH'):self.prepare(edit=lambda r,p:r[0].update(version_label='OTHER_LABEL'))
    def test_missing_approval_date_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_APPROVED'):self.prepare(edit=lambda r,p:r[2].update(approved_at=None))
    def test_duplicate_ids_block_before_query(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'DISTINCT'):L.prepare_references(no_db,(10,10,30),'.',DOC)
    def test_missing_reference_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NOT_FOUND'):L.prepare_references(lambda s,a:[],(10,20,30),'.',DOC)
    def test_tampered_bytes_blocked(self):
        def edit(rows,p):(p/'policies'/(rows[0]['content_ref'][7:]+'.json')).write_text('{}')
        with self.assertRaisesRegex(L.SettingLinksBlocked,'HASH_MISMATCH'):self.prepare(edit=edit)
    def test_boolean_is_not_numeric_policy(self):self.assertNotEqual(L._canonical(True),L._canonical(1))
    def test_decimal_and_float_have_same_semantic_value(self):self.assertEqual(L._canonical(Decimal('.30')),L._canonical(.3))
    def test_duplicate_json_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'DUPLICATE'):json.loads('{"x":1,"x":2}',object_pairs_hook=L._pairs)
    def test_nonfinite_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'NONFINITE'):L._canonical(float('nan'))
    def test_simulated_reference_blocked(self):
        r=refs();r=(replace(r[0],setting_version_id=1),*r[1:])
        with self.assertRaisesRegex(L.SettingLinksBlocked,'SIMULATED'):L.validate_references(r)
    def test_null_display_no_is_not_replaced_by_id(self):
        r=self.prepare(edit=lambda r,p:r[0].update(version_no=None));self.assertIsNone(r[0].version_no)
    def test_invalid_display_no_blocked(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'DISPLAY_NUMBER'):self.prepare(edit=lambda r,p:r[0].update(version_no=True))
    def test_inactive_flag_blocks_reference_use(self):
        with patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'legacy'}):
            with self.assertRaisesRegex(L.SettingLinksBlocked,'ACTIVATION'):L.prepare_references(no_db,(10,20,30),'.',DOC)
    def test_invalid_flag_is_not_silently_enabled(self):
        with patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'true'}):
            with self.assertRaises(L.SettingLinksBlocked):L.links_enabled()

class ReadTests(unittest.TestCase):
    def reader(self,sql,args):
        if sql.startswith('SELECT run_id,'):
            return [{'run_id':1,**dict(zip(L.FIELDS,(10,20,30)))}]
        return [dict(setting_version_id=r.setting_version_id,setting_kind=r.setting_kind,
                     version_label=r.version_label,version_no=r.version_no) for r in refs()]
    def test_legacy_uses_no_new_column_query(self):
        old={'run_id':1,'score':None,'rule_version':'v1'};r=L.attach_run_versions([old],no_db,False)[0]
        self.assertEqual(r['setting_links_status'],'NOT_DEPLOYED');self.assertIsNone(r['score']);self.assertNotIn('setting_versions',old)
    def test_three_independent_numbers_display(self):
        r=L.attach_run_versions([{'run_id':1}],self.reader,True)[0]
        self.assertEqual(r['setting_version_display'],'가중치 v2 · 기준값 v1 · 우선 확인 조건 v3')
        self.assertEqual(r[L.FIELDS[0]],10)
    def test_old_run_not_linked_by_rule_label(self):
        r=L.attach_run_versions([{'run_id':1,'rule_version':'LABEL_10'}],lambda s,a:[{'run_id':1}],True)[0]
        self.assertEqual(r['setting_versions']['weight']['status'],'UNLINKED')
    def test_unassigned_display_sequence_not_global_id(self):
        def read(s,a):
            rows=self.reader(s,a)
            if not s.startswith('SELECT run_id,'):rows[0]['version_no']=None
            return rows
        r=L.attach_run_versions([{'run_id':1}],read,True)[0]
        self.assertNotIn('가중치 v10',r['setting_version_display']);self.assertEqual(r['setting_versions']['weight']['status'],'UNNUMBERED')
    def test_wrong_kind_not_presented_as_valid(self):
        def read(s,a):
            rows=self.reader(s,a)
            if not s.startswith('SELECT run_id,'):rows[0]['setting_kind']='기준값'
            return rows
        r=L.attach_run_versions([{'run_id':1}],read,True)[0]
        self.assertEqual(r['setting_versions']['weight']['status'],'KIND_MISMATCH')
    def test_multiple_runs_are_bulk_loaded(self):
        calls=[]
        def read(s,a):calls.append(s);return self.reader(s,a)
        L.attach_run_versions([{'run_id':1},{'run_id':2}],read,True);self.assertEqual(len(calls),2)
    def test_repository_legacy_keeps_original_query(self):
        with patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'legacy'}),patch.object(db,'read_only',return_value=[{'run_id':1}]) as rd:
            r=R.PriorityRepository().list_runs(50);self.assertEqual(rd.call_count,1);self.assertEqual(r[0]['setting_links_status'],'NOT_DEPLOYED')

class WriteTests(unittest.TestCase):
    def setUp(self):self.mode=patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'v24'});self.mode.start()
    def tearDown(self):self.mode.stop()
    def write(self,c,b=None):return W.write_approved_batch(b or batch(),explicit_db_write_approval=True,evidence_by_gid=evidence(),connection_factory=lambda:c)
    def test_same_transaction_writes_and_reads_refs_period_and_details(self):
        c=Connection();r=self.write(c);self.assertEqual(r['status'],'WRITTEN');self.assertTrue(c.committed and c.closed);self.assertFalse(c.rolled)
        self.assertEqual(tuple(c.run[f] for f in L.FIELDS),(10,20,30));self.assertEqual(c.run['period_end'],date(2026,9,30));self.assertEqual(c.saved['complaint_contribution'],Decimal('-1.500000'))
    def test_changed_ref_rolls_back_before_any_insert(self):
        c=Connection('changed_ref')
        with self.assertRaisesRegex(L.SettingLinksBlocked,'CHANGED'):self.write(c)
        self.assertFalse(any(s.startswith('INSERT') for s,a in c.calls));self.assertTrue(c.rolled and c.closed)
    def test_unapplied_schema_fails_before_any_insert(self):
        c=Connection('missing_schema')
        with self.assertRaises(RuntimeError):self.write(c)
        self.assertFalse(any(s.startswith('INSERT') for s,a in c.calls));self.assertTrue(c.rolled and c.closed)
    def test_run_reference_readback_mismatch_rolls_back(self):
        c=Connection('bad_run')
        with self.assertRaisesRegex(P.ProductionBlocked,'SAVED_RUN'):self.write(c)
        self.assertTrue(c.rolled and c.closed);self.assertFalse(c.committed)
    def test_detail_readback_mismatch_still_rolls_back(self):
        c=Connection('bad_detail')
        with self.assertRaisesRegex(P.ProductionBlocked,'SAVED_DETAIL'):self.write(c)
        self.assertTrue(c.rolled and c.closed);self.assertFalse(c.committed)
    def test_inactive_mode_connects_no_database(self):
        with patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'legacy'}):
            with self.assertRaisesRegex(P.ProductionBlocked,'ACTIVATION'):
                W.write_approved_batch(batch(),explicit_db_write_approval=True,evidence_by_gid=evidence(),connection_factory=no_db)
    def test_missing_references_connects_no_database(self):
        with self.assertRaisesRegex(L.SettingLinksBlocked,'THREE_EXPLICIT'):
            W.write_approved_batch(replace(batch(),setting_references=()),explicit_db_write_approval=True,evidence_by_gid=evidence(),connection_factory=no_db)
    def test_simulated_base_stays_blocked(self):
        with self.assertRaisesRegex(P.ProductionBlocked,'SIMULATION'):
            W.write_approved_batch(replace(batch(),setting_version_id=1),explicit_db_write_approval=True,evidence_by_gid=evidence(),connection_factory=no_db)
    def test_explicit_write_gate_stays_blocked(self):
        with self.assertRaisesRegex(P.ProductionBlocked,'EXPLICIT'):
            W.write_approved_batch(batch(),explicit_db_write_approval=False,evidence_by_gid=evidence(),connection_factory=no_db)
    def test_reference_identity_changes_fingerprint(self):
        b=batch();other=(replace(b.setting_references[0],setting_version_id=11),*b.setting_references[1:])
        self.assertNotEqual(P.plan(b)['fingerprint'],P.plan(replace(b,setting_references=other))['fingerprint'])
    def test_invalid_period_is_blocked(self):
        with self.assertRaisesRegex(P.ProductionBlocked,'PERIOD'):P.plan(replace(batch(),period_end=None))
    def test_dependency_inspection_checks_actual_three_reference_rows(self):
        c=Connection('changed_ref');cur=Cursor(c)
        def reader(sql,args):
            cur.execute(sql,args);return cur.fetchall()
        with self.assertRaisesRegex(L.SettingLinksBlocked,'CHANGED'):P.inspect_dependencies(reader,batch())

class PreservationTests(unittest.TestCase):
    def function(self,path,name):
        return next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
    def test_calculation_and_d05_body_preserved(self):
        before=HERE/'fixtures/current_operational_scoring.py'
        after=CODE_ROOT/'app/services/scoring/operational_scoring.py'
        self.assertEqual(ast.dump(self.function(before,'assemble_official_score')),ast.dump(self.function(after,'assemble_official_score')))
    def test_candidate_permission_and_response_functions_preserved(self):
        before=HERE/'fixtures/current_priority_api.py';after=CODE_ROOT/'app/api/priority_api.py'
        for name in ['_scope','_candidate','candidates','candidate','run_evidence','decision_basis']:
            with self.subTest(name=name):
                b=ast.parse(before.read_bytes());a=ast.parse(after.read_bytes())
                names={n.name for n in b.body if isinstance(n,ast.FunctionDef)}
                if name in names:self.assertEqual(ast.dump(self.function(before,name)),ast.dump(self.function(after,name)))
    def test_ai07_verified_source_preserved(self):
        raw=(CODE_ROOT/'app/services/ai07/read_only_db.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'6b439fb99581c71acbbf8bfacc3ee85e0d0cb284abe7ceb7dcd6fedf4f1337a2')
    def test_approved_input_contract_preserved(self):
        self.assertEqual((HERE/'fixtures/current_approved_inputs.py').read_bytes(),(CODE_ROOT/'app/services/scoring/approved_inputs.py').read_bytes())

class PipelineTests(unittest.TestCase):
    def test_verified_references_flow_to_same_official_batch(self):
        pipeline=importlib.import_module('app.services.scoring.official_pipeline')
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'v24'}):
            path=Path(d);rows=registry(path)
            doc=copy.deepcopy(DOC);doc['policy']['label']='TEST_ONLY_POLICY'
            raw=json.dumps(doc).encode();digest=hashlib.sha256(raw).hexdigest()
            (path/'policies'/(digest+'.json')).write_bytes(raw)
            base=dict(setting_version_id=2,setting_kind='가중치',version_label='TEST_ONLY_POLICY',
                      content_ref='sha256:'+digest,approval_status='승인',approved_at=datetime(2026,10,30))
            def reader(sql,args):return rows if ' IN (' in sql else [base]
            references=L.prepare_references(reader,(10,20,30),path,doc)
            inputs=pipeline.OfficialInputs(setting_version_id=2,policy_evidence_dir=str(path),build_id='TEST_ONLY_BUILD',
                start=date(2021,1,1),end=date(2026,9,30),gids=frozenset(['TEST_GRID']),
                reviewed_complaints=({'complaint_id':'TEST_ONLY_1','gid':'TEST_GRID','received_date':'2021-01-02',
                    'review_status':'CONFIRMED','relevance':'Y','ped_type':'TEST_TYPE','low_confidence':False},),
                scored_candidates=({**batch().candidates[0],'complaint_cnt':1,'complaint_cnt_excl_low':1},),
                evidence_by_gid=evidence(),authorized_by='TEST_ONLY',approval_reference='TEST_ONLY',setting_references=references)
            with patch.object(pipeline,'write_approved_batch',return_value={'status':'WRITTEN','run_id':42}) as wr:
                result=pipeline.run_official_pipeline(inputs,explicit_db_write_approval=True,read_only=reader)
            saved=wr.call_args.args[0]
            self.assertEqual(saved.setting_references,references);self.assertEqual(saved.period_end,inputs.end)
            self.assertEqual(result['complaint_count_in_period'],1)
    def test_api_run_output_keeps_old_values_and_adds_metadata(self):
        tree=ast.parse((CODE_ROOT/'app/api/priority_api.py').read_bytes())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_run','_iso','_cnt')]
        env={'datetime':datetime};exec(compile(ast.Module(body=nodes,type_ignores=[]),'api_run','exec'),env)
        original={'run_id':1,'rule_version':'KEEP_EXISTING_LABEL','build_id':'63','setting_version_display':'가중치 v2',
                  'setting_links_status':'LINKED','weight_setting_version_id':10,'candidate_cnt':730}
        r=env['_run'](original)
        self.assertEqual(r['rule_version'],'KEEP_EXISTING_LABEL');self.assertEqual(r['candidate_cnt'],730)
        self.assertEqual(r['weight_setting_version_id'],10);self.assertEqual(r['setting_version_display'],'가중치 v2')

if __name__=='__main__':unittest.main()
