"""Existing writer regressions aligned with current D10/three-FK/DB8 contract."""
from dataclasses import replace
import pytest
from app.services.scoring.mysql_writer import write_approved_batch
from app.services.scoring.production_writer import ProductionBlocked
from app.services.priority.db8_details import COLS
from priority_mock_support import FakeDB, batch_and_evidence, create

@pytest.fixture(autouse=True)
def current_contract(monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_SETTING_LINKS','v24')


def prepared(mode=None):
    db=FakeDB();create(db);db.mode=mode
    b,ev=batch_and_evidence(db,source=None)
    return db,b,ev


def call(db,b,ev,approval=True):
    return write_approved_batch(b,explicit_db_write_approval=approval,
        evidence_by_gid=ev,connection_factory=db.connect,existing_run_id=2)


def test_explicit_consent_blocks_without_db_access():
    db,b,ev=prepared();before=len(db.connections)
    with pytest.raises(ProductionBlocked,match='EXPLICIT_DB_WRITE_APPROVAL_REQUIRED'):
        call(db,b,ev,False)
    assert len(db.connections)==before


def test_success_transaction_and_fields():
    db,b,ev=prepared();out=call(db,b,ev);c=db.connections[-1]
    assert out['run_id']==2 and out['candidate_count']==2 and out['evidence_count']==2
    assert (c.commits,c.rollbacks,c.closed)==(1,0,1)
    assert len(db.candidates)==2
    assert all(set(COLS)<=row.keys() and row['note'] is None for row in db.candidates.values())


def test_setting_not_approved_rolls_back():
    db,b,ev=prepared();db.settings[0]['approval_status']='PENDING'
    with pytest.raises(ValueError,match='NOT_APPROVED'):call(db,b,ev)
    c=db.connections[-1];assert (c.commits,c.rollbacks,c.closed)==(0,1,1)


def test_bad_candidate_blocked_without_db_access():
    db,b,ev=prepared();before=len(db.connections)
    b=replace(b,candidates=({**b.candidates[0],'input_status':'EXPLORATORY_PROXY'},b.candidates[1]))
    with pytest.raises(ProductionBlocked,match='UNVERIFIED_COMPLAINT_INPUT'):call(db,b,ev)
    assert len(db.connections)==before


def test_evidence_failure_rolls_back_entire_run():
    db,b,ev=prepared('insert_fail')
    with pytest.raises(RuntimeError,match='INJECTED'):call(db,b,ev)
    assert not db.candidates and db.connections[-1].rollbacks==1


def test_candidate_count_mismatch_rolls_back():
    # Simulate a readback mismatch after the inserts, not a populated run before them.
    db,b,ev=prepared();original=db.connect
    def factory():
        c=original();cursor=c.cursor
        def wrapped():
            cur=cursor();execute=cur.execute
            def altered(sql,args=()):
                execute(sql,args)
                if sql.startswith('SELECT COUNT(*) AS n FROM priority_candidate') and c.candidates:cur.result=[{'n':999}]
            cur.execute=altered;return cur
        c.cursor=wrapped;return c
    db.connect=factory
    with pytest.raises(ProductionBlocked,match='SAVED_ROW_COUNT_MISMATCH'):call(db,b,ev)
    assert not db.candidates and db.connections[-1].rollbacks==1


def test_detail_count_mismatch_rolls_back():
    db,b,ev=prepared();original=db.connect
    def factory():
        c=original();cursor=c.cursor
        def wrapped():
            cur=cursor();execute=cur.execute
            def altered(sql,args=()):
                execute(sql,args)
                if sql.startswith('SELECT gid,'):cur.result=[]
            cur.execute=altered;return cur
        c.cursor=wrapped;return c
    db.connect=factory
    with pytest.raises(ProductionBlocked,match='SAVED_DETAIL_GRID_SET_MISMATCH'):call(db,b,ev)
    assert not db.candidates and db.connections[-1].rollbacks==1


def test_missing_evidence_blocked_before_db():
    db,b,_=prepared();before=len(db.connections)
    with pytest.raises(ProductionBlocked,match='DETAIL_EVIDENCE_REQUIRED'):call(db,b,None)
    assert len(db.connections)==before


def test_partial_evidence_blocked_before_db():
    db,b,_=prepared();before=len(db.connections)
    with pytest.raises(ProductionBlocked,match='DETAIL_GRID_SET_MISMATCH'):call(db,b,{})
    assert len(db.connections)==before


def test_missing_detail_field_blocked_before_db():
    db,b,ev=prepared();del ev['MOCK_0']['confidence_grade']
    with pytest.raises(ProductionBlocked,match='DETAIL_EIGHT_FIELDS_REQUIRED'):call(db,b,ev)


def test_fingerprint_changes_with_result_and_evidence():
    db,b,ev=prepared();first=call(db,b,ev)
    db,b,ev=prepared();b=replace(b,candidates=tuple({**c,'official_score':51} for c in b.candidates));second=call(db,b,ev)
    db,b,ev=prepared();ev['MOCK_0']['domain_scores']['exposure']=0.6;third=call(db,b,ev)
    assert len({first['fingerprint'],second['fingerprint'],third['fingerprint']})==3
