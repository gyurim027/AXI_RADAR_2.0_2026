"""HTTP -> real proposal SQL/I07 -> setting links -> Fake D10/DB78.

SQLite supplies isolated transactional SQL; MySQL advisory locks are mocked.
This does not attest a real DB approval, deployment, or MySQL lock behavior.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import ast
import pytest
from test_approvals_api import env, headers, Cursor, Connection
from app.core import db
from app.services.scoring import setting_links as links
from app.services.scoring.policy_preflight import preflight_policy

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'_priority_next_execution/r01_hazard_policy_approved_20261101_033116_004891/integrated_policy_draft_hazard_missing_approved.json'
RAW=POLICY.read_bytes();SHA=sha256(RAW).hexdigest()


@pytest.fixture
def setup(env,monkeypatch,tmp_path):
    c,raw=env;root=tmp_path/'policies_volume'
    monkeypatch.setenv('RADAR_POLICY_EVIDENCE_DIR',str(root))
    original_execute=Cursor.execute;original_one=Cursor.fetchone;original_all=Cursor.fetchall;calls=[]
    def execute(self,sql,args=()):
        calls.append(sql);self.named_result=None;self.named_rows=None
        if sql.startswith('SELECT GET_LOCK'):
            self.named_result={'acquired':1};return
        if sql.startswith('SELECT RELEASE_LOCK'):
            self.named_result={'released':1};return
        if 'INFORMATION_SCHEMA.TABLES' in sql:
            self.named_rows=[{'table_name':t,'engine':'InnoDB'} for t in ('setting_version','access_audit')];return
        return original_execute(self,sql,args)
    def one(self):
        if getattr(self,'named_result',None) is not None:return self.named_result
        return original_one(self)
    def all_rows(self):
        if getattr(self,'named_rows',None) is not None:return self.named_rows
        return original_all(self)
    monkeypatch.setattr(Cursor,'execute',execute);monkeypatch.setattr(Cursor,'fetchone',one)
    monkeypatch.setattr(Cursor,'fetchall',all_rows)
    return c,raw,root,calls


def payload():return {'policyDocument':RAW.decode('utf8'),'expectedSha256':SHA}
def post(c,body=None,role='operator',uid=7):
    return c.post('/api/settings/proposals',headers=headers(role,uid),json=payload() if body is None else body)
def snapshot(raw):
    with raw() as con:
        return [dict(r) for r in con.execute('SELECT * FROM setting_version ORDER BY setting_version_id')],list(con.execute('SELECT * FROM access_audit'))


def test_production_main_registers_new_router_without_replacing_existing_routes():
    tree=ast.parse((ROOT/'app/main.py').read_text(encoding='utf8'))
    modules=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='ROUTER_MODULES' for t in n.targets))
    for module in ('app.api.settings_api','app.api.approvals_api','app.api.setting_proposals_api'):
        assert [m[1] for m in modules].count(module)==1


def test_preflight_has_no_db_or_file_side_effects(setup,monkeypatch):
    c,raw,root,calls=setup
    monkeypatch.setattr(db,'connect',lambda:1/0)
    r=c.post('/api/settings/proposals/preflight',headers=headers('operator',7),json=payload())
    assert r.status_code==200 and r.json()['validation']['rawSha256']==SHA
    assert not r.json()['proposalCreated'] and not root.exists() and not calls


def test_three_kinds_one_transaction_actor_audit_and_existing_get_contract(setup):
    c,raw,root,calls=setup;before,_=snapshot(raw)
    r=post(c);assert r.status_code==201
    body=r.json();rows=body['proposals'];ids=[x['settingVersionId'] for x in rows]
    assert len(set(ids))==3 and min(ids)>1
    assert [x['settingKind'] for x in rows]==list(links.KINDS)
    assert all(x['proposedBy']==7 and x['approvalStatus']=='제안' and x['approvedBy'] is None and x['approvedAt'] is None for x in rows)
    assert all(x['contentRef']=='sha256:'+SHA for x in rows)
    assert not body['approvalCreated'] and not body['scoringAuthorized'] and not body['recalculationStarted']
    after,audits=snapshot(raw);assert after[:len(before)]==before and len(audits)==3
    assert (root/'policies'/f'{SHA}.json').read_bytes()==RAW
    assert c.get(f'/api/settings/versions/{ids[0]}',headers=headers('operator',7)).json()['approvalStatus']=='제안'
    assert c.post('/api/settings/versions',headers=headers('operator',7),json={}).status_code==405
    assert not any(t in sql for sql in calls for t in ('priority_run','priority_candidate','job_run'))


@pytest.mark.parametrize('role',['city','district'])
def test_wrong_role_cannot_propose(setup,role):
    c,raw,root,calls=setup
    assert post(c,role=role).status_code==403
    assert not root.exists() and not calls and len(snapshot(raw)[0])==6


def test_anonymous_cannot_propose(setup):
    c,raw,root,calls=setup
    assert c.post('/api/settings/proposals',json=payload()).status_code==401
    assert not calls


@pytest.mark.parametrize('field,value',[('proposedBy',900),('approvedBy',22),('approvalStatus','승인'),('settingKind','가중치'),('policyDir','/tmp/other')])
def test_actor_approval_and_path_spoofing_rejected(setup,field,value):
    c,raw,root,calls=setup;body=payload();body[field]=value
    assert post(c,body).status_code==422
    assert not calls and len(snapshot(raw)[0])==6


@pytest.mark.parametrize('mode',['raw_tamper','review_hash','missing_rule','duplicate_json_key','nonfinite'])
def test_bad_policy_never_opens_database(setup,mode):
    c,raw,root,calls=setup;body=payload()
    if mode=='raw_tamper':body['policyDocument']+=' '
    if mode=='review_hash':body['expectedSha256']=preflight_policy(RAW,expected_sha256=SHA)['review_components']['기준값']['sha256']
    if mode=='missing_rule':
        d=json.loads(RAW);del d['inside_hazard_unobserved'];body['policyDocument']=json.dumps(d)
        body['expectedSha256']=sha256(body['policyDocument'].encode()).hexdigest()
    if mode=='duplicate_json_key':
        body['policyDocument']='{"x":1,"x":2}';body['expectedSha256']=sha256(body['policyDocument'].encode()).hexdigest()
    if mode=='nonfinite':
        body['policyDocument']='{"x":NaN}';body['expectedSha256']=sha256(body['policyDocument'].encode()).hexdigest()
    assert post(c,body).status_code==422
    assert not calls and not root.exists()


def test_byte_size_limit_and_unconfigured_storage(setup,monkeypatch):
    c,raw,root,calls=setup;body=payload();body['policyDocument']='가'*50000
    assert post(c,body).status_code==413 and not calls
    monkeypatch.delenv('RADAR_POLICY_EVIDENCE_DIR')
    assert post(c).status_code==503 and not calls


def test_retry_returns_same_ids_without_extra_audits(setup):
    c,raw,root,calls=setup;a=post(c);b=post(c)
    assert (a.status_code,b.status_code)==(201,200)
    assert b.json()['alreadyExists'] and a.json()['settingVersionIds']==b.json()['settingVersionIds']
    assert len(snapshot(raw)[0])==9 and len(snapshot(raw)[1])==3


def test_parallel_retries_create_one_bundle_sqlite_serialization_only(setup):
    c,raw,root,calls=setup
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(lambda _:post(c),range(2)))
    assert sorted(x.status_code for x in out)==[200,201]
    assert out[0].json()['settingVersionIds']==out[1].json()['settingVersionIds']
    assert len(snapshot(raw)[0])==9 and len(snapshot(raw)[1])==3


@pytest.mark.parametrize('kind',['second_insert','audit'])
def test_failure_rolls_back_all_three_and_audits(setup,kind):
    c,raw,root,calls=setup;before=snapshot(raw)
    with raw() as con:
        if kind=='second_insert':con.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON setting_version WHEN NEW.setting_kind='기준값' BEGIN SELECT RAISE(ABORT,'fake failure'); END")
        else:con.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON access_audit BEGIN SELECT RAISE(ABORT,'fake failure'); END")
    assert post(c).status_code==500
    assert snapshot(raw)==before and any('RELEASE_LOCK' in s for s in calls)


def test_readback_mismatch_rolls_back_proposals_and_audits(setup,monkeypatch):
    c,raw,root,calls=setup;before=snapshot(raw);original=Cursor.fetchall
    def corrupt(self):
        rows=original(self)
        if rows and all(r.get('setting_version_id',0)>6 for r in rows):rows[0]['version_label']='CORRUPT'
        return rows
    monkeypatch.setattr(Cursor,'fetchall',corrupt)
    assert post(c).status_code==409 and snapshot(raw)==before


def test_lost_commit_response_recovered_by_idempotent_retry(setup,monkeypatch):
    c,raw,root,calls=setup;original=Connection.commit;count=[0]
    def lose(self):
        original(self);count[0]+=1
        if count[0]==1:raise RuntimeError('PRIVATE_DRIVER_ERROR')
    monkeypatch.setattr(Connection,'commit',lose)
    r=post(c);assert r.status_code==503 and r.json()['error']['code']=='proposal_commit_unconfirmed'
    assert 'PRIVATE_DRIVER_ERROR' not in r.text
    assert post(c).status_code==200 and len(snapshot(raw)[0])==9 and len(snapshot(raw)[1])==3


def test_advisory_lock_unavailable_does_not_write(setup,monkeypatch):
    c,raw,root,calls=setup;original=Cursor.fetchone
    def busy(self):
        if getattr(self,'named_result',None)=={'acquired':1}:return {'acquired':0}
        return original(self)
    monkeypatch.setattr(Cursor,'fetchone',busy)
    assert post(c).status_code==503 and len(snapshot(raw)[0])==6 and not root.exists()


def test_corrupt_immutable_evidence_not_overwritten(setup):
    c,raw,root,calls=setup;p=root/'policies'/f'{SHA}.json';p.parent.mkdir(parents=True);p.write_bytes(b'corrupt')
    assert post(c).status_code==503 and p.read_bytes()==b'corrupt'
    assert len(snapshot(raw)[0])==6 and not snapshot(raw)[1]


def test_nontransactional_audit_table_blocks_before_insert(setup,monkeypatch):
    c,raw,root,calls=setup;original=Cursor.fetchall
    def engines(self):
        rows=original(self)
        if rows and rows[0].get('table_name'):
            return [{'table_name':'setting_version','engine':'InnoDB'},
                    {'table_name':'access_audit','engine':'MyISAM'}]
        return rows
    monkeypatch.setattr(Cursor,'fetchall',engines)
    response=post(c)
    assert response.status_code==503 and response.json()['error']['code']=='proposal_transaction_engine_required'
    assert len(snapshot(raw)[0])==6 and not snapshot(raw)[1]


def test_partial_bundle_is_not_silently_filled(setup):
    c,raw,root,calls=setup;label=json.loads(RAW)['policy']['label']
    with raw() as con:
        con.execute("INSERT INTO setting_version VALUES (90,'가중치',?,?,7,CURRENT_TIMESTAMP,'제안',NULL,NULL,NULL)",(label,'sha256:'+SHA))
    before=snapshot(raw);r=post(c)
    assert r.status_code==409 and r.json()['error']['code']=='proposal_bundle_incomplete_or_ambiguous'
    assert snapshot(raw)==before


def test_returned_proposal_is_not_recreated(setup):
    c,raw,root,calls=setup;r=post(c);sid=r.json()['proposals'][0]['settingVersionId']
    assert c.post(f'/api/approvals/{sid}/review',headers=headers(),json={'decision':'돌려보냄','reviewComment':'근거 보완'}).status_code==200
    before=snapshot(raw);r=post(c)
    assert r.status_code==409 and r.json()['error']['code']=='proposal_previously_returned'
    assert snapshot(raw)==before


def test_self_approval_denied_after_role_change(setup):
    c,raw,root,calls=setup;r=post(c);sid=r.json()['proposals'][0]['settingVersionId'];before=snapshot(raw)
    response=c.post(f'/api/approvals/{sid}/review',headers=headers('city',7),json={'decision':'승인'})
    assert response.status_code==403 and response.json()['error']['code']=='self_approval_not_allowed'
    assert snapshot(raw)==before


def test_http_proposal_review_setting_links_d10_and_db78_join(setup,monkeypatch):
    c,raw,root,calls=setup;r=post(c);ids=tuple(x['settingVersionId'] for x in r.json()['proposals'])
    for sid in ids:
        response=c.post(f'/api/approvals/{sid}/review',headers=headers(),json={'decision':'승인'})
        assert response.status_code==200 and not response.json()['recalculationStarted']
    monkeypatch.setenv('RADAR_PRIORITY_SETTING_LINKS','v24')
    doc=links.read_document({'content_ref':'sha256:'+SHA,'version_label':json.loads(RAW)['policy']['label']},root)
    refs=links.prepare_references(db.read_only,ids,root,doc)
    assert tuple(x.setting_version_id for x in refs)==ids
    from priority_mock_support import FakeDB,receipt,request,batch_and_evidence
    from app.services.d10_run_creation import create_d10_run
    from app.services.scoring.mysql_writer import write_approved_batch
    fake=FakeDB()
    with raw() as con:
        by_id={r['setting_version_id']:dict(r) for r in con.execute('SELECT * FROM setting_version')}
    fake.settings=[{**by_id[i],'version_no':None} for i in ids]
    req=replace(request(),weight_setting_version_id=ids[0],threshold_setting_version_id=ids[1],priority_condition_setting_version_id=ids[2])
    created=create_d10_run(req,explicit_creation_approval=True,connection_factory=fake.connect,source_audit=receipt())
    batch,evidence=batch_and_evidence(fake);batch=replace(batch,setting_version_id=ids[0])
    written=write_approved_batch(batch,explicit_db_write_approval=True,evidence_by_gid=evidence,
        connection_factory=fake.connect,existing_run_id=created['run_id'])
    assert written['candidate_count']==2 and fake.legacy_accesses==0
    assert fake.runs[created['run_id']]['note']=='r03:'+receipt().audit_sha256
    retry=post(c);assert retry.status_code==200 and retry.json()['allApproved']
    assert len(snapshot(raw)[0])==9 and len(snapshot(raw)[1])==6
