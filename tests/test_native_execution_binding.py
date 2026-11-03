from copy import deepcopy
from datetime import date
from dataclasses import replace
import unittest
import os
from unittest.mock import patch
from app.services.d10_run_creation import RunCreation,create_d10_run,D10RunBlocked,SETTING_FIELDS
from app.services.scoring.mysql_writer import write_approved_batch
from app.services.scoring.production_writer import OfficialBatch,ProductionBlocked
from app.services.scoring.setting_links import _validated_row,KINDS
from app.services.priority.db8_details import COLS,JSON_INDEXES
from test_input_builds import Store,Connection,Cursor,register,approve,START,END,POLICY,AUDIT
from app.services.scoring.input_builds import load_native_scoring_input, BuildBlocked
from app.services.priority.lineage import read_run_lineage
LABEL='RADAR_TEAM_DRAFT_PENDING_APPROVAL'
class NativeStore(Store):
 def __init__(self):
  super().__init__();self.runs={};self.candidates={};self.width=33;self.legacy_accesses=0
  for r in self.settings.values():r.update(version_label=LABEL,version_no=None)
 def connect(self):c=NativeConnection(self);self.connections.append(c);return c
class NativeConnection(Connection):
 def __init__(self,s):super().__init__(s);self.run_save=deepcopy(s.runs);self.candidate_save=deepcopy(s.candidates)
 def cursor(self):return NativeCursor(self)
 def rollback(self):super().rollback();self.s.runs=deepcopy(self.run_save);self.s.candidates=deepcopy(self.candidate_save)
class NativeCursor(Cursor):
 def execute(self,sql,args=()):
  s=self.c.s;q=sql.lower();self.result=[]
  if 'from setting_version' in q:
   s.calls.append((sql,args));self.result=[deepcopy(s.settings[i]) for i in args if i in s.settings];return
  if ('from priority_run where run_id=%s' in q or 'from priority_candidate where run_id=%s' in q) and args[0]==1:
   s.legacy_accesses+=1;raise AssertionError('run1 accessed')
  if "table_name='priority_run'" in q:
   s.calls.append((sql,args))
   if "column_name='run_id'" in q:self.result=[{'EXTRA':''}]
   elif 'column_type as column_type' in q:self.result=[dict(table_name='priority_run',column_name=k,column_type=f'varchar({v})') for k,v in [('build_id',30),('rule_version',s.width),('note',300)]]
   else:self.result=[{'COLUMN_NAME':c} for c in ['run_id','build_id','rule_version','created_at','note','period_start','period_end',*SETTING_FIELDS]]
   return
  if 'information_schema.columns' in q:
   s.calls.append((sql,args));self.result=[dict(name=c,data_type='json' if i in JSON_INDEXES else 'decimal' if i in (4,6) else 'varchar',nullable='YES',column_type='json' if i in JSON_INDEXES else 'decimal(18,6)' if i in (4,6) else 'varchar(40)' if i==3 else 'varchar(255)') for i,c in enumerate(COLS)];return
  if 'coalesce(max(run_id)' in q:s.calls.append((sql,args));self.result=[{'next_id':max([1,*s.runs])+1}];return
  if q.startswith('insert into priority_run'):
   s.calls.append((sql,args));rid,build,rule,note,start,end,*ids=args;s.runs[rid]=dict(run_id=rid,build_id=build,rule_version=rule,note=note,period_start=start,period_end=end,**dict(zip(SETTING_FIELDS,ids)));return
  if 'from priority_run where run_id=%s' in q:s.calls.append((sql,args));self.result=[deepcopy(s.runs[args[0]])] if args[0] in s.runs else [];return
  if 'from grid_feature where id_gid=' in q:s.calls.append((sql,args));self.result=[dict(ID_gid=g['ID_gid']) for g in s.grids if g['ID_gid']==args[0]];return
  if q.startswith('select count(*) as n from priority_candidate'):
   s.calls.append((sql,args));self.result=[{'n':sum(rid==args[0] for rid,g in s.candidates)}];return
  if q.startswith('insert into priority_candidate'):
   s.calls.append((sql,args));columns=sql.partition('(')[2].partition(')')[0].split(',');row=dict(zip(columns,args));key=(row['run_id'],row['gid'])
   if key in s.candidates:raise RuntimeError('duplicate mock key')
   s.candidates[key]=row;return
  if q.startswith('select gid,'):
   s.calls.append((sql,args));self.result=[deepcopy(r) for (rid,g),r in s.candidates.items() if rid==args[0]];return
  return super().execute(sql,args)
def create(s,r):
 return create_d10_run(RunCreation(r['build_id'],LABEL,START,END,52,53,54),explicit_creation_approval=True,connection_factory=s.connect)
def batch(s,r):
 refs=tuple(_validated_row(s.settings[i],k) for i,k in zip((52,53,54),KINDS))
 rows=tuple(dict(gid=g,official_score=50,rank_no=1,selected_yn='N',complaint_cnt=1 if g=='g1' else 0,complaint_cnt_excl_low=1 if g=='g1' else 0,calculation_status='OFFICIAL',input_status='VERIFIED_CLASSIFIED',classification_status='COMPLETE',cond_result_yn=None,cond_hazard_yn=None,cond_exposure_yn=None,cond_vulnerable_yn=None,matched_roles=None) for i,g in enumerate(('g1','g2')))
 ev={x['gid']:dict(domain_scores={'hazard':None,'exposure':50},indicator_contributions={'mock':50},unevaluated_reasons=['MOCK_ONLY'],confidence_grade='UNVERIFIED',score_excluding_accidents=50,exclusion_reasons=[],complaint_contribution=0,policy_version=LABEL) for x in rows}
 return OfficialBatch(r['build_id'],LABEL,52,'sha256:'+POLICY,'a'*64,POLICY,'b'*64,rows,'MOCK_OPERATOR','MOCK_ONLY_APPROVAL',refs,START,END,AUDIT),ev
class Tests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'v24'});self.env.start();self.addCleanup(self.env.stop)
 def ready(self):
  s=NativeStore();r=register(s);approve(s,r);return s,r
 def test_registration_approval_d10_writer_fake_flow(self):
  s,r=self.ready();out=create(s,r);self.assertEqual(out['run_id'],2);self.assertEqual(s.runs[2]['note'],'r03:'+AUDIT)
  b,e=batch(s,r);result=write_approved_batch(b,explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=s.connect,existing_run_id=2)
  self.assertEqual(result['status'],'WRITTEN');self.assertEqual(len(s.candidates),2);self.assertEqual(s.legacy_accesses,0)
 def test_deployed_30_width_stops_before_insert(self):
  s,r=self.ready();s.width=30
  with self.assertRaisesRegex(D10RunBlocked,'TEXT_CAPACITY_EXCEEDED:rule_version'):create(s,r)
  self.assertFalse(s.runs);self.assertEqual(s.legacy_accesses,0)
 def test_no_source_approval_cannot_create(self):
  s=NativeStore();r=register(s)
  with self.assertRaises(D10RunBlocked):create(s,r)
  self.assertFalse(s.runs)
 def test_source_changes_cannot_create(self):
  s,r=self.ready();s.source[0]['received_date']=date(2026,1,2)
  with self.assertRaises(D10RunBlocked):create(s,r)
  self.assertFalse(s.runs)
 def test_current_grid_changed_after_creation_cannot_store(self):
  s,r=self.ready();create(s,r);s.grids[0]['feature']=90;b,e=batch(s,r)
  with self.assertRaises(ProductionBlocked):write_approved_batch(b,explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=s.connect,existing_run_id=2)
  self.assertFalse(s.candidates)
 def test_candidate_counts_mismatch_cannot_store(self):
  s,r=self.ready();create(s,r);b,e=batch(s,r);rows=deepcopy(b.candidates);rows[0]['complaint_cnt']=99;b=replace(b,candidates=rows)
  with self.assertRaisesRegex(ProductionBlocked,'COMPLAINT_COUNTS_MISMATCH'):write_approved_batch(b,explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=s.connect,existing_run_id=2)
  self.assertFalse(s.candidates)
 def test_duplicate_writer_run_not_reused(self):
  s,r=self.ready();create(s,r);b,e=batch(s,r)
  kw=dict(explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=s.connect,existing_run_id=2)
  write_approved_batch(b,**kw)
  with self.assertRaisesRegex(ProductionBlocked,'ALREADY_HAS_CANDIDATES'):write_approved_batch(b,**kw)
  self.assertEqual(len(s.candidates),2)
 def test_native_input_loader_returns_current_rows_without_writes(self):
  s,r=self.ready();create(s,r)
  p=load_native_scoring_input(run_id=2,build_id=r['build_id'],setting_ids=(52,53,54),start=START,end=END,expected_audit_sha256=AUDIT,connection_factory=s.connect)
  self.assertTrue(p['current_input_verified']);self.assertEqual(len(p['_inputs']['_source_rows']),3);self.assertEqual(s.connections[-1].commits,0)
 def test_native_input_loader_rejects_run1_before_connection(self):
  s=NativeStore()
  with self.assertRaises(BuildBlocked):load_native_scoring_input(run_id=1,build_id='db59:64',setting_ids=(52,53,54),start=START,end=END,expected_audit_sha256=AUDIT,connection_factory=s.connect)
  self.assertFalse(s.connections)
 def test_native_input_loader_rejects_filled_round(self):
  s,r=self.ready();create(s,r);s.candidates[(2,'g1')]={'run_id':2}
  with self.assertRaisesRegex(BuildBlocked,'ALREADY_HAS_CANDIDATES'):load_native_scoring_input(run_id=2,build_id=r['build_id'],setting_ids=(52,53,54),start=START,end=END,expected_audit_sha256=AUDIT,connection_factory=s.connect)
 def test_existing_lineage_api_service_reads_native_row_id(self):
  s,r=self.ready();create(s,r);calls=[]
  def reader(sql,args=()):
   calls.append((sql,args))
   if 'INFORMATION_SCHEMA.COLUMNS' in sql:return [{'name':k} for k in ('row_id','table_name','file','rows','cols','built_at','script','note')]
   if 'FROM priority_run' in sql:return [deepcopy(s.runs[i]) for i in args if i in s.runs]
   if 'FROM setting_version' in sql:return [deepcopy(s.settings[i]) for i in args if i in s.settings]
   if 'FROM build_info' in sql:return [deepcopy(s.builds[i]) for i in args if i in s.builds]
   raise AssertionError('Unexpected lookup SQL')
  result=read_run_lineage(2,reader)
  self.assertEqual(result['build_info']['status'],'MANIFEST_BINDING_VERIFIED');self.assertFalse(result['end_to_end_verified'])
  self.assertTrue(any('FROM build_info WHERE row_id=%s' in q for q,a in calls));self.assertFalse(any('FROM build_info WHERE build_id=' in q for q,a in calls))
if __name__=='__main__':unittest.main()
