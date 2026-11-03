from copy import deepcopy
from datetime import date
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest
from app.services.scoring.approved_inputs import InputBlocked
from app.services.scoring.r02_exception_link import reconcile_exceptions
from app.services.scoring.r02_full_source_quarantine import prepare_full_source_r02
from app.services.scoring.source_audit_lineage import SourceAuditBlocked

START,END=date(2021,1,1),date(2026,9,30)
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('closeout_command',ROOT/'scripts/r02_closeout_check.py')
command=importlib.util.module_from_spec(spec);spec.loader.exec_module(command)

def source():
    base={'received_date':'2026-09-01','gid':'G1','class_method':'AI','low_confidence':False}
    return [{**base,'complaint_id':'PRIVATE_1','relevance':None,'ped_type':None},
            {**base,'complaint_id':'PRIVATE_2','gid':None,'relevance':None,'ped_type':None},
            {**base,'complaint_id':'PRIVATE_3','relevance':'Y','ped_type':'장애물'},
            {**base,'complaint_id':'PRIVATE_4','relevance':'N','ped_type':None}]

def audit(rows):
    full=prepare_full_source_r02(rows,gids={'G1','G2'},start=START,end=END,
        mapped_exclusion_policy=True,unmapped_quarantine_policy=True)
    return json.dumps(full.audit).encode(),full.audit['audit_sha256']

def go(rows=None,failed=None,original=None):
    rows=source() if rows is None else rows
    raw,h=audit(rows if original is None else original)
    return reconcile_exceptions(
        [{'cid':'PRIVATE_1','status':'mask_failed'},{'cid':'PRIVATE_2','status':'error'}] if failed is None else failed,
        iter(rows),gids={'G1','G2'},audit_raw=raw,expected_audit_sha256=h,
        checkpoint_sha256='a'*64,start=START,end=END,
        expected_statuses={'mask_failed':1,'error':1})

def test_join_proves_same_manifests_and_no_eligible_leakage():
    report=go()
    assert report['status']=='PASS'
    assert report['exception_buckets']==dict(mapped_excluded=1,unmapped_quarantined=1,
        eligible=0,missing=0,classification_changed=0)
    assert report['matched_exception_count']==2
    assert 'PRIVATE_' not in json.dumps(report)
    assert not report['official_write_authorized']
    before=report.pop('report_sha256')
    assert before==sha256(json.dumps(report,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def test_comparison_does_not_call_aggregate_or_modify_input(monkeypatch):
    rows=source();original=deepcopy(rows);raw,h=audit(rows)
    import app.services.scoring.approved_inputs as inputs
    monkeypatch.setattr(inputs,'aggregate_reviewed_complaints',lambda *a,**k:1/0)
    report=reconcile_exceptions([{'cid':'PRIVATE_1','status':'mask_failed'}],rows,
        gids={'G1','G2'},audit_raw=raw,expected_audit_sha256=h,checkpoint_sha256='a'*64,
        start=START,end=END,expected_statuses={'mask_failed':1})
    assert rows==original and report['classification_rerun']==0

@pytest.mark.parametrize('cid',['PRIVATE_3','ABSENT'])
def test_eligible_or_absent_exception_blocks(cid):
    with pytest.raises(InputBlocked,match='NOT_SAFELY_QUARANTINED'):
        go(failed=[{'cid':cid,'status':'mask_failed'},{'cid':'PRIVATE_2','status':'error'}])

def test_same_counts_with_different_excluded_identity_blocks():
    rows=source();original=deepcopy(rows);rows[0]['complaint_id']='CHANGED_ID'
    with pytest.raises(InputBlocked,match='MANIFEST_CHANGED'):go(rows,original=original)

def test_changed_null_classification_blocks_even_if_bucket_unchanged():
    rows=source();rows[0]['relevance']='불명'
    with pytest.raises(InputBlocked,match='NOT_SAFELY_QUARANTINED'):go(rows)

@pytest.mark.parametrize('mode',['duplicate_exception','duplicate_source','unknown_grid','out_of_period','wrong_status','wrong_counts'])
def test_bad_populations_fail_closed(mode):
    rows=source();failed=[{'cid':'PRIVATE_1','status':'mask_failed'},{'cid':'PRIVATE_2','status':'error'}]
    original=deepcopy(rows)
    if mode=='duplicate_exception':failed[1]['cid']='PRIVATE_1'
    if mode=='duplicate_source':rows.append(deepcopy(rows[0]))
    if mode=='unknown_grid':rows[0]['gid']='ALIEN'
    if mode=='out_of_period':rows[0]['received_date']='2020-01-01'
    if mode=='wrong_status':failed[0]['status']='ok'
    if mode=='wrong_counts':rows=rows[:-1]
    with pytest.raises(InputBlocked):go(rows,failed=failed,original=original)

def test_audit_tamper_blocks():
    rows=source();raw,h=audit(rows);d=json.loads(raw);d['source_rows']=100
    with pytest.raises(SourceAuditBlocked):
        reconcile_exceptions([],rows,gids={'G1','G2'},audit_raw=json.dumps(d).encode(),
            expected_audit_sha256=h,checkpoint_sha256='a'*64,start=START,end=END)

@pytest.fixture
def checkpoint(tmp_path):
    p=tmp_path/'final.sqlite3';c=sqlite3.connect(p)
    c.execute('CREATE TABLE result(cid TEXT PRIMARY KEY,status TEXT)')
    c.execute('CREATE TABLE source(cid TEXT PRIMARY KEY)')
    c.executemany('INSERT INTO result VALUES (?,?)',((f'ok{i}','ok') for i in range(160352)))
    c.executemany('INSERT INTO result VALUES (?,?)',((f'fail{i}','mask_failed' if i<75 else 'error') for i in range(76)))
    c.execute('INSERT INTO source SELECT cid FROM result');c.commit();c.close()
    return p

def test_checkpoint_read_only_bytes_unchanged(checkpoint):
    before=checkpoint.read_bytes();rows,h=command.read_checkpoint(checkpoint)
    assert len(rows)==76 and len(h)==64 and checkpoint.read_bytes()==before
    assert {r['status'] for r in rows}=={'mask_failed','error'}

def test_checkpoint_includes_stable_committed_wal(checkpoint):
    writer=sqlite3.connect(checkpoint)
    try:
        assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
        writer.execute("UPDATE result SET status=status WHERE cid='fail0'");writer.commit()
        before=command.checkpoint_digest(checkpoint)
        rows,digest=command.read_checkpoint(checkpoint)
        assert len(rows)==76 and digest==before==command.checkpoint_digest(checkpoint)
    finally:writer.close()

def test_final_checkpoint_discovery(checkpoint):
    p,rows,h=command.find_checkpoint(checkpoint.parent)
    assert p==checkpoint and len(rows)==76 and h==command.checkpoint_digest(p)

def test_checkpoint_exception_must_belong_to_source_population(checkpoint):
    c=sqlite3.connect(checkpoint)
    c.execute("UPDATE source SET cid='OTHER_PRIVATE' WHERE cid='fail0'");c.commit();c.close()
    with pytest.raises(command.CollectionBlocked,match='ABSENT_FROM_SOURCE'):
        command.read_checkpoint(checkpoint)

def test_wrong_checkpoint_population_rejected(tmp_path):
    p=tmp_path/'bad.db';c=sqlite3.connect(p);c.execute('CREATE TABLE result(cid,status)');c.commit();c.close()
    with pytest.raises(command.CollectionBlocked,match='POPULATION'):command.read_checkpoint(p)

def test_sql_allowlist_never_allows_db77_or_writes():
    session=command.ReadSession(None)
    for kind in ('priority_run','write','UPDATE','DELETE','DDL'):
        with pytest.raises(command.CollectionBlocked,match='NOT_ALLOWED'):session.cursor(kind)
    with pytest.raises(command.CollectionBlocked,match='NOT_ALLOWED'):
        session.reference_reader('SELECT * FROM priority_run WHERE run_id=1',())

def test_db62_check_continues_when_checkpoint_missing(tmp_path,monkeypatch):
    project=tmp_path/'project';(project/'app').mkdir(parents=True)
    for rel in (command.POLICY_PATH,command.AUDIT_PATH):
        target=project/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/rel).read_bytes())
    def unavailable(*a):raise command.CollectionBlocked('FINAL_CHECKPOINT_NOT_FOUND')
    monkeypatch.setattr(command,'find_checkpoint',unavailable)
    calls=[]
    class Cursor:
        def execute(self,sql,args):calls.append(sql);self.sql=sql
        def fetchall(self):
            if 'INFORMATION_SCHEMA' in self.sql:
                return [{'TABLE_NAME':t,'ENGINE':'InnoDB'} for t in ('setting_version','src_complaint','grid_feature')]
            return []
        def close(self):pass
    class Connection:
        def cursor(self):return Cursor()
        def rollback(self):calls.append('ROLLBACK')
        def close(self):calls.append('CLOSE')
        def commit(self):raise AssertionError('COMMIT_FORBIDDEN')
    report,path=command.run(project,connection_factory=Connection)
    assert report['status']=='BLOCKED'
    assert report['stages']['db62']['executed']
    assert not report['stages']['exception_link']['executed']
    assert any('FROM setting_version WHERE content_ref' in sql for sql in calls)
    assert not any('priority_run' in sql for sql in calls)
    assert calls[-2:]==['ROLLBACK','CLOSE'] and path.is_file()

def test_errors_do_not_export_driver_secrets():
    assert command.safe_reason(RuntimeError('password=SECRET, host=PRIVATE'))=='RuntimeError'
