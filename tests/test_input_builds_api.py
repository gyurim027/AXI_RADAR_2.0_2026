from unittest.mock import patch
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import input_builds_api as api
from app.core.auth import current_user
from app.core.responses import install_error_handlers, CamelCaseMiddleware
from app.core import db
from test_input_builds import Store,AUDIT,POLICY,register,approve
from app.services.scoring import input_builds
class Tests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.app=FastAPI();install_error_handlers(self.app);self.app.add_middleware(CamelCaseMiddleware);self.app.include_router(api.router)
  self.client=TestClient(self.app,headers={'X-Response-Case':'snake'})
  self.patch=patch.object(db,'raw_connection',self.store.connect);self.patch.start()
  self.body=dict(periodStart='2021-01-01',periodEnd='2026-09-30',expectedAuditSha256=AUDIT,policySha256=POLICY,settingIds=[52,53,54])
 def tearDown(self):self.client.close();self.patch.stop()
 def actor(self,role,uid=8):self.app.dependency_overrides[current_user]=lambda:dict(user_id=uid,role=role)
 def test_unauthenticated_401(self):
  self.assertEqual(self.client.post('/api/input-builds',json=self.body).status_code,401);self.assertFalse(self.store.builds)
 def test_city_cannot_register(self):
  self.actor('city');self.assertEqual(self.client.post('/api/input-builds',json=self.body).status_code,403)
 def test_operator_cannot_review(self):
  self.actor('operator');self.assertEqual(self.client.post('/api/input-builds/64/review',json={'expectedManifestSha256':'1'*64}).status_code,403)
 def test_unknown_fields_rejected(self):
  self.actor('operator');self.body['approvedBy']=9;self.assertEqual(self.client.post('/api/input-builds',json=self.body).status_code,422)
 def test_boolean_setting_id_rejected(self):
  self.actor('operator');self.body['settingIds'][0]=True;self.assertEqual(self.client.post('/api/input-builds',json=self.body).status_code,422)
 def test_role_derived_actor_and_separate_review(self):
  self.actor('operator');r=self.client.post('/api/input-builds',json=self.body);self.assertEqual(r.status_code,200);out=r.json()
  self.assertEqual(self.store.events[0]['actor_ref'],8);self.assertFalse(out['official_run_created'])
  self.actor('city',9);r=self.client.post('/api/input-builds/64/review',json={'expectedManifestSha256':out['manifest_sha256']});self.assertEqual(r.status_code,200);self.assertTrue(r.json()['audit_approved'])
 def test_self_approval_409(self):
  self.actor('operator');out=self.client.post('/api/input-builds',json=self.body).json();self.actor('city',8)
  r=self.client.post('/api/input-builds/64/review',json={'expectedManifestSha256':out['manifest_sha256']});self.assertEqual(r.status_code,409);self.assertEqual(len(self.store.events),1)
 def test_commit_loss_503_and_no_retry(self):
  self.actor('operator');self.store.mode='commitlost';r=self.client.post('/api/input-builds',json=self.body)
  self.assertEqual(r.status_code,503);self.assertEqual(len(self.store.connections),1)
 def test_route_paths_no_calculation_or_round_creation(self):
  routes=self.app.openapi()['paths'];self.assertEqual(set(routes),{'/api/input-builds','/api/input-builds/{row_id}/review','/api/input-builds/{row_id}'})
 def test_status_lookup_does_not_promote_execution(self):
  r=register(self.store);approve(self.store,r);self.actor('operator')
  def reader(sql,args):
   con=self.store.connect()
   try:
    with con.cursor() as cur:cur.execute(sql,args);return cur.fetchall()
   finally:con.rollback();con.close()
  with patch.object(api,'read_build_status',lambda i:input_builds.read_build_status(i,reader)):
   response=self.client.get('/api/input-builds/64')
  self.assertEqual(response.status_code,200);self.assertTrue(response.json()['audit_approved']);self.assertFalse(response.json()['current_input_verified']);self.assertNotIn('actor_ref',response.text)
if __name__=='__main__':unittest.main()
