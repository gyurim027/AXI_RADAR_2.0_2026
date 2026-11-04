from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
import sys,os,unittest
from unittest.mock import patch
from app.core import job_run
from app.services.scoring.input_builds import BuildBlocked
from app.services.scoring.engine_rerun import ReplayBlocked
from scripts import run_official_priority as command
from test_input_builds import SOURCE,GRIDS,AUDIT
from test_official_priority_job_tracking import MemoryStore
class Tests(unittest.TestCase):
 def args(self):return ['run_official_priority','--existing-run-id','3','--setting-id','52','--policy-dir','MOCK_ONLY','--weight-setting-id','52','--threshold-setting-id','53','--priority-condition-setting-id','54','--native-full-source','--expected-audit-sha256',AUDIT,'--start','2021-01-01','--end','2026-09-30','--build-id','db59:64','--authorized-by','MOCK_OPERATOR','--approval-reference','MOCK_REFERENCE','--commit-official']
 def execute(self,args=None,load_error=None):
  store=MemoryStore();calls=[];full=object()
  def runner(**kw):calls.append(kw);return {'status':'WRITTEN','run_id':3,'candidate_count':2}
  def reader(sql,params):
   self.assertIn('FROM job_run WHERE job_run_id=',sql);return [{'status':store.status,'ref_table':store.ref_table,'ref_id':store.ref_id}]
  def loader(**kw):
   if load_error:raise load_error
   return {'_inputs':{'_source_rows':SOURCE,'_grid_rows':GRIDS,'_full_source_input':full}}
  with patch.dict(os.environ,{'RADAR_PRIORITY_SETTING_LINKS':'v24'}),patch.object(sys,'argv',args or self.args()),patch.object(job_run,'_store',store),patch.object(command.db,'read_only',reader),patch.object(command,'run_from_live_rows',runner),patch('app.services.scoring.input_builds.load_native_scoring_input',side_effect=loader),redirect_stdout(StringIO()),redirect_stderr(StringIO()):
   try:command.main();error=None
   except (SystemExit,BuildBlocked,ReplayBlocked) as exc:error=exc
  return store,calls,full,error
 def test_native_source_reaches_engine_and_db85_ref(self):
  # This test checks the command -> scoring bridge. Receipt durability has its own tests.
  # Mocking it here must never change the actual run-id protection in engine_rerun.py.
  with patch.object(command,'save_replay_receipt') as receipt:
   store,calls,full,error=self.execute()
  self.assertIsNone(error)
  self.assertEqual(len(calls),1)
  self.assertIs(calls[0]['r02_full_source_input'],full)
  self.assertEqual(store.ref_table,'priority_run')
  self.assertEqual(str(store.ref_id),'3')
  self.assertEqual(store.status,job_run.SUCCESS)
  receipt.assert_called_once()
 def test_legacy_run2_replay_receipt_remains_blocked(self):
  # Keep the production protection: no receipt or scoring on run 2.
  args=self.args()
  args[args.index('--existing-run-id')+1]='2'
  store,calls,full,error=self.execute(args)
  self.assertIsInstance(error,ReplayBlocked)
  self.assertFalse(calls)
 def test_unverified_native_input_before_job(self):
  store,calls,full,error=self.execute(load_error=BuildBlocked('MOCK_MISSING_APPROVAL'));self.assertIsInstance(error,BuildBlocked);self.assertFalse(store.started);self.assertFalse(calls)
 def test_run1_rejected_before_loader_or_job(self):
  args=self.args();args[args.index('--existing-run-id')+1]='1';store,calls,full,error=self.execute(args);self.assertIsInstance(error,SystemExit);self.assertFalse(store.started);self.assertFalse(calls)
 def test_expected_audit_required_before_job(self):
  args=self.args();i=args.index('--expected-audit-sha256');del args[i:i+2];store,calls,full,error=self.execute(args);self.assertIsInstance(error,SystemExit);self.assertFalse(store.started)
if __name__=='__main__':unittest.main()
