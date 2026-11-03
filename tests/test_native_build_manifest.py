import json, unittest
from copy import deepcopy
from datetime import date,datetime,timezone
from pathlib import Path
from app.services.scoring import native_build_manifest as n
from app.services.scoring.source_audit_lineage import verify_source_audit
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'_priority_next_execution/r02_full_source_quarantine_20261101_012021/full_source_policy_audit.json'
SHA='abed6e98e083564e935a11d50f4142dc99ae5aa67823c5112c7c012fe85f857f'
def audit():return verify_source_audit(AUDIT.read_bytes(),expected_sha256=SHA,start=date(2021,1,1),end=date(2026,9,30),grid_count=2406)
def record(**extra):
 args=dict(source_snapshot_sha256='1'*64,grid_snapshot_sha256='2'*64,eligible_counts_sha256='3'*64,source_rows=281153,grid_rows=2406,grid_columns=108,policy_sha256='f28a608c2593750b44dce44ddb5f68128df229e7eb0b00082c963d0ac545da81',setting_ids=(52,53,54),audit=audit(),built_at=datetime(2026,11,1,tzinfo=timezone.utc));args.update(extra)
 return {'row_id':64,**n.plan_native_build(**args)}
def run():return dict(run_id=2,build_id='db59:64',note='r03:'+SHA,period_start=date(2021,1,1),period_end=date(2026,9,30),**dict(zip(n.SETTING_FIELDS,(52,53,54))))
class Tests(unittest.TestCase):
 def test_native_existing_columns_only(self):
  r=record();self.assertEqual(set(r),{'row_id','table_name','file','rows','cols','built_at','script','note'});self.assertNotIn('build_id',r)
 def test_metadata_binding_never_promotes_approval(self):
  v=n.verify_native_binding(run(),record());self.assertEqual(v['status'],'MANIFEST_BINDING_VERIFIED');self.assertFalse(v['source_snapshot_recomputed']);self.assertFalse(v['official_write_authorized']);self.assertFalse(v['end_to_end_verified'])
 def test_reader_selects_one_native_row(self):
  seen=[]
  def reader(sql,args):seen.append((sql,args));return [record()]
  n.read_native_binding(run(),reader);self.assertEqual(len(seen),1);self.assertEqual(seen[0][1],(64,));self.assertNotIn('build_id',seen[0][0])
 def test_legacy_run_blocks_before_reader(self):
  r=run();r['run_id']=1
  with self.assertRaisesRegex(n.NativeBuildBlocked,'LEGACY'):n.read_native_binding(r,lambda *a:self.fail('reader called'))
 def test_native_id_fits_deployed_30(self):self.assertLessEqual(len(n.native_build_id(9223372036854775807)),30)
 def test_invalid_native_ids(self):
  for i in (True,0,-1,'64',2**63):
   with self.assertRaises(n.NativeBuildBlocked):n.native_build_id(i)
 def test_invalid_reference_blocks_before_read(self):
  for value in ('oldbuild','db59:064','db59:64 OR 1=1','db59:9223372036854775808'):
   r=run();r['build_id']=value
   with self.assertRaises(n.NativeBuildBlocked):n.read_native_binding(r,lambda *a:self.fail('reader called'))
 def test_missing_row_blocks(self):
  with self.assertRaises(n.NativeBuildBlocked):n.read_native_binding(run(),lambda *a:[])
 def test_duplicate_row_blocks(self):
  with self.assertRaises(n.NativeBuildBlocked):n.read_native_binding(run(),lambda *a:[record(),record()])
 def test_content_tamper_blocks(self):
  r=record();d=json.loads(r['note']);d['source_rows']+=1;r['note']=json.dumps(d)
  with self.assertRaisesRegex(n.NativeBuildBlocked,'HASH_MISMATCH'):n.read_manifest(r)
 def test_unknown_payload_field_blocks(self):
  r=record();d=json.loads(r['note']);d['complaint_text']='not permitted';r['note']=json.dumps(d)
  with self.assertRaises(n.NativeBuildBlocked):n.read_manifest(r)
 def test_existing_reference_record_not_reinterpreted(self):
  r=record();r['table_name']='src_complaint'
  with self.assertRaisesRegex(n.NativeBuildBlocked,'LEGACY'):n.read_manifest(r)
 def test_row_count_mismatch(self):
  r=record();r['rows']=2405
  with self.assertRaises(n.NativeBuildBlocked):n.read_manifest(r)
 def test_source_hash_cannot_be_audit_hash(self):
  with self.assertRaisesRegex(n.NativeBuildBlocked,'NOT_SOURCE_SNAPSHOT'):record(source_snapshot_sha256=SHA)
 def test_audit_source_counts_bound(self):
  with self.assertRaises(n.NativeBuildBlocked):record(source_rows=281152)
 def test_three_distinct_settings_required(self):
  with self.assertRaises(n.NativeBuildBlocked):record(setting_ids=(52,52,54))
 def test_time_requires_zone(self):
  with self.assertRaises(n.NativeBuildBlocked):record(built_at=datetime(2026,11,1))
 def test_run_policy_setting_mismatch(self):
  r=run();r['threshold_setting_version_id']=52
  with self.assertRaises(n.NativeBuildBlocked):n.verify_native_binding(r,record())
 def test_run_period_mismatch(self):
  r=run();r['period_end']=date(2026,8,31)
  with self.assertRaises(n.NativeBuildBlocked):n.verify_native_binding(r,record())
 def test_run_audit_mismatch(self):
  r=run();r['note']='r03:'+'0'*64
  with self.assertRaises(n.NativeBuildBlocked):n.verify_native_binding(r,record())
 def test_run_row_reference_mismatch(self):
  r=run();r['build_id']='db59:65'
  with self.assertRaises(n.NativeBuildBlocked):n.verify_native_binding(r,record())
 def test_actual_rule_label_does_not_fit_30(self):
  schema=[dict(table_name='priority_run',column_name=k,column_type=f'varchar({v})') for k,v in [('build_id',30),('rule_version',30),('note',300)]]
  with self.assertRaisesRegex(n.NativeBuildBlocked,'EXCEEDED:rule_version'):n.validate_run_text_capacity(schema,build_id='db59:64',rule_version='RADAR_TEAM_DRAFT_PENDING_APPROVAL',note='r03:'+SHA)
 def test_capacity_check_does_not_truncate(self):
  schema=[dict(table_name='priority_run',column_name=k,column_type=f'varchar({v})') for k,v in [('build_id',30),('rule_version',33),('note',300)]]
  v=n.validate_run_text_capacity(schema,build_id='db59:64',rule_version='RADAR_TEAM_DRAFT_PENDING_APPROVAL',note='r03:'+SHA);self.assertFalse(v['values_truncated'])
if __name__=='__main__':unittest.main()
