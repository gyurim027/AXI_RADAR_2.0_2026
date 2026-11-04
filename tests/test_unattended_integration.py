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

@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_SETTING_LINKS','v24')


from priority_mock_support import receipt, request, rows, FakeDB, FakeConnection, FakeCursor, batch_and_evidence, create, write


def test_real_policy_hash_and_three_actual_projections(tmp_path):
    r=store_policy_evidence(POLICY.read_bytes(),tmp_path,expected_sha256=POLICY_SHA)
    assert r['official_content_ref']=='sha256:'+POLICY_SHA
    assert set(r['review_components'])==set(L.KINDS)
    assert not r['db62_registered'] and not r['approval_created']
    assert (tmp_path/'policies'/f'{POLICY_SHA}.json').read_bytes()==POLICY.read_bytes()
    store_policy_evidence(POLICY.read_bytes(),tmp_path,expected_sha256=POLICY_SHA)

@pytest.mark.parametrize('mutation',['remove','change','boolean'])
def test_rule_missing_or_changed_blocked(mutation):
    doc=json.loads(POLICY.read_bytes())
    if mutation=='remove':del doc['inside_hazard_unobserved']
    elif mutation=='change':doc['inside_hazard_unobserved']='invented_rule'
    else:doc['hazard_missing_rule_approved_by_user']=False
    raw=json.dumps(doc).encode()
    with pytest.raises(PolicyPreflightBlocked):preflight_policy(raw,expected_sha256=sha256(raw).hexdigest())

@pytest.mark.parametrize('kind',L.KINDS)
def test_actual_components_detect_each_change(kind):
    raw=POLICY.read_bytes();docs={k:raw for k in L.KINDS};d=json.loads(raw)
    if kind=='가중치':d['policy']['domain_weights']['hazard']=0.4
    elif kind=='기준값':del d['inside_hazard_unobserved']
    else:d['d05_rule']['thresholds']['hazard']=0.7
    docs[kind]=json.dumps(d).encode()
    with pytest.raises(PolicyPreflightBlocked):compare_components(raw,docs)


def test_raw_tamper_and_review_hash_cannot_be_content_ref():
    with pytest.raises(PolicyPreflightBlocked):preflight_policy(POLICY.read_bytes()+b' ',expected_sha256=POLICY_SHA)
    review=preflight_policy(POLICY.read_bytes(),expected_sha256=POLICY_SHA)['review_components']['기준값']['sha256']
    with pytest.raises(PolicyPreflightBlocked):preflight_policy(POLICY.read_bytes(),expected_sha256=review)


def test_stored_policy_corruption_not_overwritten(tmp_path):
    path=tmp_path/'policies'/f'{POLICY_SHA}.json';path.parent.mkdir();path.write_bytes(b'bad')
    with pytest.raises(PolicyPreflightBlocked):store_policy_evidence(POLICY.read_bytes(),tmp_path,expected_sha256=POLICY_SHA)
    assert path.read_bytes()==b'bad'


def test_actual_audit_hash_roundtrip_and_counts(tmp_path):
    r=receipt();p=store_source_audit(r,tmp_path)
    assert revalidate_source_audit(r,start=START,end=END)==r
    assert json.loads(p.read_bytes())['source_rows']==281153
    assert r.grid_count==2406
    with pytest.raises(SourceAuditBlocked):verify_run_binding(2,'r03:'+'0'*64,r)
    assert verify_run_binding(2,source_audit_note(AUDIT_SHA),r)['source_snapshot_verified'] is False

@pytest.mark.parametrize('field,value',[('source_rows',281154),('grid_count',2),('approved_for_official_write',True)])
def test_audit_tamper_rejected(field,value):
    d=json.loads(AUDIT.read_bytes());d['audit'][field]=value
    with pytest.raises(SourceAuditBlocked):verify_source_audit(json.dumps(d).encode(),expected_sha256=AUDIT_SHA,start=START,end=END)


def test_audit_period_mismatch():
    with pytest.raises(SourceAuditBlocked):verify_source_audit(AUDIT.read_bytes(),expected_sha256=AUDIT_SHA,start=START,end=date(2026,8,31))


def test_actual_creator_binds_audit_and_three_fks_without_legacy_read():
    db=FakeDB();out=create(db,receipt());run=db.runs[out['run_id']]
    assert out['run_id']==2 and out['source_audit_sha256']==AUDIT_SHA
    assert run['note']=='r03:'+AUDIT_SHA and [run[f] for f in SETTING_FIELDS]==[2,3,4]
    assert not out['scoring_authorized'] and not out['review_opened']
    assert db.legacy_accesses==0

@pytest.mark.parametrize('mode',['lock_fail','missing_schema','bad_run_readback'])
def test_creator_failure_no_partial_run(mode):
    db=FakeDB(mode)
    with pytest.raises(D10RunBlocked):create(db,receipt())
    assert db.runs=={} and db.connections[0].commits==0 and db.connections[0].rollbacks==1
    assert db.connections[0].closed==1

@pytest.mark.parametrize('rid',[1,0,2**63])
def test_allocator_invalid_ids_blocked(rid):
    db=FakeDB();db.next_id=rid
    with pytest.raises(D10RunBlocked):create(db,receipt())
    assert not db.runs and db.legacy_accesses==0


def test_creation_requires_approval_before_connection():
    with pytest.raises(D10RunBlocked):create_d10_run(request(),connection_factory=lambda:1/0)


def test_unapproved_settings_and_duplicate_fks_blocked():
    db=FakeDB();db.settings[1]['approval_status']='PENDING'
    with pytest.raises(D10RunBlocked):create(db,receipt())
    with pytest.raises(D10RunBlocked):create_d10_run(replace(request(),threshold_setting_version_id=2),explicit_creation_approval=True,connection_factory=lambda:1/0)


def test_source_note_collision_and_period_mismatch_before_connection():
    with pytest.raises(D10RunBlocked):create_d10_run(replace(request(),note='KEEP_EXISTING_NOTE'),explicit_creation_approval=True,source_audit=receipt(),connection_factory=lambda:1/0)
    with pytest.raises(SourceAuditBlocked):create_d10_run(replace(request(),period_end=date(2026,8,31)),explicit_creation_approval=True,source_audit=receipt(),connection_factory=lambda:1/0)


def test_real_writer_success_8_fields_and_existing_note_contract():
    db=FakeDB();create(db,receipt());out=write(db)
    assert out['status']=='WRITTEN' and out['candidate_count']==2
    assert all(set(COLS)<=r.keys() for r in db.candidates.values())
    # Current source stores DB78 details directly; preserve existing note=None.
    assert all(r['note'] is None for r in db.candidates.values())
    assert all(r['cond_result_yn'] is None for r in db.candidates.values())
    assert db.legacy_accesses==0


def test_duplicate_batch_blocked_and_no_extra_candidates():
    db=FakeDB();create(db,receipt());write(db)
    with pytest.raises(ProductionBlocked,match='ALREADY_HAS_CANDIDATES'):write(db)
    assert len(db.candidates)==2 and db.connections[-1].rollbacks==1

@pytest.mark.parametrize('mode,exception',[('insert_fail',RuntimeError),('bad_count',ProductionBlocked),('bad_detail',ProductionBlocked)])
def test_writer_failure_rolls_back_candidates(mode,exception):
    db=FakeDB();create(db,receipt());db.mode=mode
    with pytest.raises(exception):write(db)
    assert not db.candidates and len(db.runs)==1
    assert db.connections[-1].rollbacks==1 and db.connections[-1].commits==0


def test_audit_mismatch_blocks_writer():
    db=FakeDB();create(db,receipt());db.runs[2]['note']='r03:'+'0'*64
    with pytest.raises(ProductionBlocked,match='SOURCE_AUDIT_MISMATCH'):write(db)
    assert not db.candidates


def test_run1_blocked_before_any_sql():
    db=FakeDB()
    with pytest.raises(ProductionBlocked,match='LEGACY_RUN1'):write(db,rid=1)
    assert db.calls==[]
    with pytest.raises(SourceAuditBlocked):verify_run_binding(1,'r03:'+AUDIT_SHA,receipt())


def test_fingerprint_binds_audit():
    db=FakeDB();b,_=batch_and_evidence(db)
    assert plan(b)['fingerprint']!=plan(replace(b,source_audit_sha256='0'*64))['fingerprint']


def test_full_source_real_pipeline_preview_integration(tmp_path):
    # Source rows and score values below are synthetic; actual policy bytes unchanged.
    full=prepare_full_source_r02([],gids={'MOCK_0','MOCK_1'},start=START,end=END,
                                mapped_exclusion_policy=True,unmapped_quarantine_policy=True)
    r=verify_source_audit(json.dumps(full.audit).encode(),expected_sha256=full.audit['audit_sha256'],start=START,end=END)
    store_policy_evidence(POLICY.read_bytes(),tmp_path,expected_sha256=POLICY_SHA)
    db=FakeDB();create(db,r);b,ev=batch_and_evidence(db,source=r.audit_sha256)
    inp=OfficialInputs(2,str(tmp_path),'MOCK_BUILD',START,END,frozenset(ev),(),b.candidates,ev,
                       'MOCK_OPERATOR','MOCK_APPROVAL',b.setting_references,2)
    out=run_official_pipeline(inp,explicit_db_write_approval=False,read_only=db.reader,
                              connection_factory=lambda:1/0,r02_full_source_input=full,preview_only=True)
    assert out['status']=='VALIDATED_NOT_WRITTEN' and out['source_audit_sha256']==r.audit_sha256
    assert not db.candidates
    # The existing full-source official write gate remains intact.
    with pytest.raises(ValueError,match='FULL_SOURCE_OFFICIAL_WRITES_BLOCKED'):
        run_official_pipeline(inp,explicit_db_write_approval=True,read_only=db.reader,r02_full_source_input=full)
    with pytest.raises(ValueError,match='LEGACY_RUN1'):
        run_official_pipeline(replace(inp,existing_run_id=1),explicit_db_write_approval=False,read_only=lambda *a:1/0,preview_only=True)


def test_actual_audit_binding_with_2406_synthetic_candidates():
    db=FakeDB();create(db,receipt());b,e=batch_and_evidence(db,grids=2406)
    out=write_approved_batch(b,explicit_db_write_approval=True,evidence_by_gid=e,connection_factory=db.connect,existing_run_id=2)
    assert out['candidate_count']==out['evidence_count']==2406
    assert db.runs[2]['note']=='r03:'+AUDIT_SHA and db.legacy_accesses==0


def test_source_lineage_readback_and_tamper(tmp_path):
    from app.services.scoring.source_audit_lineage import read_source_lineage
    db=FakeDB();create(db,receipt());path=store_source_audit(receipt(),tmp_path)
    proof=read_source_lineage(2,tmp_path,db.reader)
    assert proof['source_audit_sha256']==AUDIT_SHA and proof['aggregate_audit_verified']
    assert proof['source_snapshot_verified'] is False
    path.write_bytes(b'{}')
    with pytest.raises(SourceAuditBlocked):read_source_lineage(2,tmp_path,db.reader)
    with pytest.raises(SourceAuditBlocked):read_source_lineage(1,tmp_path,lambda *a:1/0)


def test_preview_cannot_grant_write_approval():
    with pytest.raises(ValueError,match='PREVIEW_CANNOT_AUTHORIZE'):
        run_official_pipeline(None,explicit_db_write_approval=True,preview_only=True)


def test_cli_forwards_fresh_d10_run_id(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import sys
    from scripts import run_official_priority as command
    export=tmp_path/'mock_review.json'
    export.write_text(json.dumps([{'complaint_id':'MOCK_C1','gid':'MOCK_0','received_date':'2026-09-01','relevance':'N','class_method':'AI'}]))
    monkeypatch.chdir(tmp_path)
    calls=[]
    def read(sql,args=()):
        if 'FROM grid_feature' in sql:return [{'ID_gid':'MOCK_0'}]
        if 'FROM src_complaint' in sql:return [{'complaint_id':'MOCK_C1','gid':'MOCK_0'}]
        if 'FROM job_run' in sql:return [{'status':command.job_run.SUCCESS,'ref_table':'priority_run','ref_id':'88'}]
        raise AssertionError('UNEXPECTED_CLI_SQL')
    @contextmanager
    def track(*args,**kwargs):
        yield SimpleNamespace(run_id=501,ref=lambda *a:None,rows=lambda *a:None)
    def run(**kwargs):
        calls.append(kwargs)
        return {'status':'WRITTEN','run_id':88,'candidate_count':1}
    monkeypatch.setattr(command.db,'read_only',read)
    monkeypatch.setattr(command,'track',track)
    monkeypatch.setattr(command,'run_from_live_rows',run)
    # This test checks CLI argument forwarding, not DB85 replay evidence.
    # Keep the production guard intact; verify the receipt boundary is called.
    def accept_receipt(job_id, args, read_only):
        assert job_id==501
        assert args.existing_run_id==88
    monkeypatch.setattr(command,'save_replay_receipt',accept_receipt)
    monkeypatch.setattr(sys,'argv',['run_official_priority','--existing-run-id','88','--setting-id','2',
        '--policy-dir',str(tmp_path),'--weight-setting-id','2','--threshold-setting-id','3',
        '--priority-condition-setting-id','4','--reviewed-json',str(export),'--start','2021-01-01',
        '--end','2026-09-30','--build-id','MOCK_BUILD','--authorized-by','MOCK',
        '--approval-reference','MOCK_ONLY','--commit-official'])
    command.main()
    assert calls[0]['existing_run_id']==88
    assert calls[0]['weight_setting_version_id']==2


def test_forged_audit_receipt_rechecked_before_d10_connection():
    with pytest.raises(SourceAuditBlocked):
        create_d10_run(request(),explicit_creation_approval=True,
                       source_audit=replace(receipt(),audit_sha256='0'*64),connection_factory=lambda:1/0)
