from copy import deepcopy
from datetime import date,datetime
from hashlib import sha256
import json
import unittest
from unittest.mock import patch
from app.services.scoring import input_builds as b, native_build_manifest as n
from app.services.scoring.r02_full_source_quarantine import prepare_full_source_r02
START=date(2021,1,1);END=date(2026,9,30);POLICY='1'*64
SOURCE=[dict(complaint_id=str(i),gid=gid,received_date=date(2026,1,1),relevance=rel,class_method=method,ped_type=typ) for i,gid,rel,method,typ in [(1,'g1','Y','AI','보도'),(2,'g2',None,None,None),(3,None,'N','규칙',None)]]
for row in SOURCE:row['coord_accuracy']='보통'
GRIDS=[dict(ID_gid='g1',feature=2),dict(ID_gid='g2',feature=3)]
AUDIT=prepare_full_source_r02(SOURCE,gids={'g1','g2'},start=START,end=END,mapped_exclusion_policy=True,unmapped_quarantine_policy=True).audit['audit_sha256']
class Store:
 def __init__(self):
  self.builds={};self.events=[];self.calls=[];self.source=deepcopy(SOURCE);self.grids=deepcopy(GRIDS);self.connections=[];self.mode='ok'
  self.settings={i:dict(setting_version_id=i,setting_kind=k,content_ref='sha256:'+POLICY,approval_status='승인',approved_at='2026-11-01') for i,k in zip((52,53,54),('가중치','기준값','우선 확인 조건'))}
 def connect(self):c=Connection(self);self.connections.append(c);return c
class Connection:
 def __init__(self,s):self.s=s;self.saved=(deepcopy(s.builds),deepcopy(s.events));self.commits=0;self.rollbacks=0;self.closed=False
 def cursor(self):return Cursor(self)
 def commit(self):
  self.commits+=1
  if self.s.mode=='commitlost':raise OSError('lost')
 def rollback(self):self.rollbacks+=1;self.s.builds,self.s.events=deepcopy(self.saved)
 def close(self):self.closed=True
class Cursor:
 def __init__(self,c):self.c=c;self.result=[];self.lastrowid=None
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def execute(self,sql,args=()):
  s=self.c.s;s.calls.append((sql,args));q=' '.join(sql.lower().split());self.result=[]
  if q.startswith(('set transaction','start transaction','select release_lock')):return
  if 'information_schema.tables' in q:self.result=[dict(table_name=t,engine='MyISAM' if s.mode=='engine' and t=='build_info' else 'InnoDB') for t in ('build_info','access_audit','setting_version','src_complaint','grid_feature')];return
  if q.startswith('select get_lock'):self.result=[{'acquired':0 if s.mode=='lock' else 1}];return
  if 'from src_complaint' in q:self.result=deepcopy(s.source);return
  if 'from grid_feature' in q:self.result=deepcopy(s.grids);return
  if 'from setting_version' in q:self.result=[deepcopy(s.settings[args[0]])] if args[0] in s.settings else [];return
  if q.startswith('insert into build_info'):
   i=max([63,*s.builds])+1;row=dict(zip(('table_name','file','rows','cols','built_at','script','note'),args));row['row_id']=i;s.builds[i]=row;self.lastrowid=i;return
  if 'from build_info' in q:
   if 'where row_id=' in q:self.result=[deepcopy(s.builds[args[0]])] if args[0] in s.builds else []
   else:self.result=[deepcopy(v) for v in s.builds.values() if v['table_name']==args[0] and v['file']==args[1]]
   if s.mode=='duplicate':self.result*=2
   return
  if q.startswith('insert into access_audit'):
   if s.mode=='auditfail':raise RuntimeError('synthetic failure')
   row=dict(zip(('actor_ref','resource_kind','resource_key','access_reason'),args));row.update(access_audit_id=len(s.events)+1,accessed_at=datetime(2026,11,1));s.events.append(row);return
  if 'from access_audit' in q:
   if 'where resource_key=' in q:self.result=[deepcopy(r) for r in s.events if r['resource_key']==args[0] and r['resource_kind'] in args[1:]]
   else:self.result=[deepcopy(r) for r in s.events if (r['resource_kind'],r['resource_key'],r['access_reason'])==tuple(args)]
   return
  raise AssertionError('Unexpected SQL: '+q)
 def fetchall(self):return self.result
 def fetchone(self):return self.result[0] if self.result else None

def register(s,**kw):
 args=dict(user={'user_id':8,'role':'operator'},start=START,end=END,expected_audit_sha256=AUDIT,policy_sha256=POLICY,setting_ids=(52,53,54),explicit_registration_approval=True,connection_factory=s.connect);args.update(kw);return b.register_build(**args)
def approve(s,out,**kw):
 args=dict(expected_manifest_sha256=out['manifest_sha256'],user={'user_id':9,'role':'city'},explicit_approval=True,connection_factory=s.connect);args.update(kw);return b.approve_build(out['build_row_id'],**args)
def verify(s,out,**kw):
 con=s.connect()
 try:
  with con.cursor() as cur:
   args=dict(build_id=out['build_id'],policy_sha256=POLICY,setting_ids=(52,53,54),start=START,end=END);args.update(kw);return b.verify_execution_build(cur,**args)
 finally:con.rollback();con.close()
class Tests(unittest.TestCase):
 def test_registration_atomic_readback_and_audit_persisted(self):
  s=Store();out=register(s);self.assertEqual(out['build_id'],'db59:64');self.assertTrue(out['created']);self.assertEqual(len(s.events),1);self.assertTrue(s.connections[0].closed)
  doc=n.read_manifest(s.builds[64]);self.assertEqual(doc['source_audit_document']['audit_sha256'],AUDIT);self.assertFalse(out['scoring_authorized'])
 def test_idempotent_registration_no_duplicate_rows_or_events(self):
  s=Store();a=register(s);c=register(s);self.assertEqual(a['build_id'],c['build_id']);self.assertFalse(c['created']);self.assertEqual(len(s.events),1);self.assertEqual(len(s.builds),1)
 def test_missing_registration_authorization_before_connection(self):
  s=Store()
  with self.assertRaises(b.BuildBlocked):register(s,explicit_registration_approval=False)
  self.assertFalse(s.connections)
 def test_wrong_registration_role_before_connection(self):
  s=Store()
  with self.assertRaises(b.BuildBlocked):register(s,user={'user_id':8,'role':'city'})
  self.assertFalse(s.connections)
 def test_readonly_actor_rejected(self):
  s=Store()
  with self.assertRaises(b.BuildBlocked):register(s,user={'user_id':8,'role':'operator','read_only':True})
  self.assertFalse(s.connections)
 def test_unapproved_setting_blocks_build_insert(self):
  s=Store();s.settings[53]['approval_status']='제안'
  with self.assertRaises(b.BuildBlocked):register(s)
  self.assertFalse(s.builds)
 def test_durable_audit_failure_rolls_back_build(self):
  s=Store();s.mode='auditfail'
  with self.assertRaises(RuntimeError):register(s)
  self.assertFalse(s.builds);self.assertFalse(s.events);self.assertEqual(s.connections[0].rollbacks,1)
 def test_engine_block_before_capture(self):
  s=Store();s.mode='engine'
  with self.assertRaises(b.BuildBlocked):register(s)
  self.assertFalse(any('FROM src_complaint' in q for q,a in s.calls))
 def test_lock_failure_rolls_back(self):
  s=Store();s.mode='lock'
  with self.assertRaises(b.BuildBlocked):register(s)
  self.assertFalse(s.builds)
 def test_expected_audit_hash_mismatch_blocks_registration(self):
  s=Store()
  with self.assertRaises(ValueError):register(s,expected_audit_sha256='0'*64)
  self.assertFalse(s.builds)
 def test_separate_approval_and_execution_proof(self):
  s=Store();r=register(s);out=approve(s,r);proof=verify(s,r)
  self.assertTrue(out['audit_approved']);self.assertTrue(proof['current_input_verified']);self.assertTrue(proof['official_audit_approval_verified']);self.assertFalse(proof['official_write_authorized']);self.assertEqual(len(s.events),2)
 def test_self_approval_blocks(self):
  s=Store();r=register(s)
  with self.assertRaises(b.BuildBlocked):approve(s,r,user={'user_id':8,'role':'city'})
  self.assertEqual(len(s.events),1)
 def test_approval_missing_before_execution(self):
  s=Store();r=register(s)
  with self.assertRaises(b.BuildBlocked):verify(s,r)
 def test_approval_explicit_gate(self):
  s=Store();r=register(s)
  with self.assertRaises(b.BuildBlocked):approve(s,r,explicit_approval=False)
  self.assertEqual(len(s.events),1)
 def test_approval_hash_mismatch(self):
  s=Store();r=register(s)
  with self.assertRaises(b.BuildBlocked):approve(s,r,expected_manifest_sha256='0'*64)
  self.assertEqual(len(s.events),1)
 def test_grid_change_blocks_approval(self):
  s=Store();r=register(s);s.grids[0]['feature']=5
  with self.assertRaises(b.BuildBlocked):approve(s,r)
  self.assertEqual(len(s.events),1)
 def test_source_date_change_same_aggregate_detected(self):
  s=Store();r=register(s);s.source[0]['received_date']=date(2026,1,2)
  with self.assertRaises(b.BuildBlocked):approve(s,r)
  self.assertEqual(len(s.events),1)
 def test_source_classification_change_blocks(self):
  s=Store();r=register(s);approve(s,r);s.source[0]['relevance']='N'
  with self.assertRaises(ValueError):verify(s,r)
 def test_idempotent_approval_no_extra_event(self):
  s=Store();r=register(s);approve(s,r);out=approve(s,r);self.assertTrue(out['already_approved']);self.assertEqual(len(s.events),2)
 def test_wrong_setting_bundle_on_execution(self):
  s=Store();r=register(s);approve(s,r)
  with self.assertRaises(b.BuildBlocked):verify(s,r,setting_ids=(53,52,54))
 def test_unknown_build_prefix_before_query(self):
  s=Store();r=register(s)
  with self.assertRaises(b.BuildBlocked):verify(s,r,build_id='old:1')
 def test_source_identifiers_not_in_persisted_manifest(self):
  s=Store();r=register(s);doc=json.loads(s.builds[64]['note']);self.assertNotIn('complaint_id',json.dumps(doc));self.assertNotIn('gid',doc)
 def test_no_run_candidate_job_or_ddl_mutations(self):
  s=Store();r=register(s);approve(s,r);verify(s,r)
  writes=[q.lower() for q,a in s.calls if q.lower().startswith(('insert','update','delete','alter','create table'))]
  self.assertTrue(all(q.startswith(('insert into build_info','insert into access_audit')) for q in writes))
 def test_duplicate_approval_blocks(self):
  s=Store();r=register(s);approve(s,r);s.events.append(deepcopy(s.events[-1]))
  with self.assertRaises(b.BuildBlocked):verify(s,r)
 def test_hash_tamper_cannot_forge_approval(self):
  s=Store();r=register(s);approve(s,r);doc=json.loads(s.builds[64]['note']);doc['grid_snapshot_sha256']='5'*64;s.builds[64]['note']=n.canonical(doc).decode();s.builds[64]['file']='sha256:'+sha256(n.canonical(doc)).hexdigest()
  with self.assertRaises(b.BuildBlocked):verify(s,r)
 def test_fingerprint_reorders_stably_and_detects_duplicate(self):
  self.assertEqual(b.fingerprint(SOURCE,'complaint_id'),b.fingerprint(list(reversed(SOURCE)),'complaint_id'))
  with self.assertRaises(b.BuildBlocked):b.fingerprint(SOURCE+[SOURCE[0]],'complaint_id')
 def test_low_accuracy_is_bound_to_snapshot_and_exclusion_count(self):
  normal=b.snapshot(SOURCE,GRIDS,start=START,end=END,expected_audit_sha256=AUDIT)
  changed=deepcopy(SOURCE);changed[0]['coord_accuracy']='낮음'
  low=b.snapshot(changed,GRIDS,start=START,end=END,expected_audit_sha256=AUDIT)
  self.assertEqual(low['counts_by_gid'][0]['relevant_count'],1);self.assertEqual(low['counts_by_gid'][0]['count_excl_low'],0)
  self.assertNotEqual(normal['eligible_counts_sha256'],low['eligible_counts_sha256']);self.assertNotEqual(normal['source_snapshot_sha256'],low['source_snapshot_sha256'])
 def test_registration_commit_loss_is_explicitly_unconfirmed(self):
  s=Store();s.mode='commitlost'
  with self.assertRaises(b.BuildCommitUnconfirmed):register(s)
 def test_review_commit_loss_is_explicitly_unconfirmed(self):
  s=Store();r=register(s);s.mode='commitlost'
  with self.assertRaises(b.BuildCommitUnconfirmed):approve(s,r)
 def test_calculator_arrays_are_bound_to_registered_input(self):
  s=Store();r=register(s)
  out=b.verify_supplied_scoring_inputs(build_id=r['build_id'],grids=s.grids,source=s.source,
      policy_sha256=POLICY,setting_ids=(52,53,54),reader=lambda *a:[s.builds[64]])
  self.assertTrue(out['supplied_input_verified']);self.assertFalse(out['official_write_authorized'])
 def test_modified_arrays_cannot_reuse_valid_build_receipt(self):
  s=Store();r=register(s);grids=deepcopy(s.grids);grids[0]['feature']=100
  with self.assertRaisesRegex(b.BuildBlocked,'SUPPLIED_SCORING_GRID_MISMATCH'):
   b.verify_supplied_scoring_inputs(build_id=r['build_id'],grids=grids,source=s.source,
      policy_sha256=POLICY,setting_ids=(52,53,54),reader=lambda *a:[s.builds[64]])
if __name__=='__main__':unittest.main()
