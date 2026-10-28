from dataclasses import replace
import pytest
from app.services.scoring.mysql_writer import write_approved_batch
from app.services.scoring.production_writer import OfficialBatch, ProductionBlocked


def batch():
    return OfficialBatch(build_id='b1', rule_version='v1', setting_version_id=1,
        setting_content_ref='content1', input_digest='a'*64, policy_digest='b'*64,
        complaint_contract_digest='c'*64, authorized_by='approver', approval_reference='A-1',
        candidates=({'gid':'g1', 'calculation_status':'OFFICIAL','official_score':'72.5',
                     'input_status':'VERIFIED_CLASSIFIED', 'classification_status':'COMPLETE',
                     'source_kind':'OFFICIAL','rank_no':1,'complaint_cnt':2,
                     'complaint_cnt_excl_low':1,'selected_yn':'Y'},))


def evidence():
    return {'g1': {'domain_scores': {'hazard': 72},
                    'indicator_contributions': {'indicator_1': 12.5},
                    'unevaluated_reasons': [], 'confidence_grade': 'HIGH',
                    'score_excluding_accidents': 60}}


@pytest.fixture(autouse=True)
def isolated_evidence_directory(tmp_path, monkeypatch):
    # Writer uses a real file-sidecar; isolate every test without changing production settings.
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path / 'evidence'))


class Cursor:
    def __init__(self, c): self.c=c; self.lastrowid=12; self.result=[]
    def execute(self, sql, args=()):
        self.c.sql.append((sql,args))
        if 'FROM setting_version' in sql:
            self.result=[{'approval_status':self.c.status,'approved_at':'today',
                          'content_ref':'content1','version_label':'v1'}]
        elif 'FROM grid_feature' in sql: self.result=[{'ID_gid':'g1'}]
        elif 'FROM priority_run' in sql: self.result=[]
        elif 'COUNT(*)' in sql:
            self.result=[{'n': self.c.detail_count if 'note LIKE' in sql else self.c.count}]
        else: self.result=[]
        if self.c.fail_insert and 'INSERT INTO priority_candidate ' in sql:
            raise RuntimeError('simulated evidence DB failure')
    def fetchall(self): return self.result
    def __enter__(self): return self
    def __exit__(self, *a): pass


class Connection:
    def __init__(self, status='APPROVED', count=1, detail_count=1, fail_insert=False):
        self.status=status; self.count=count; self.detail_count=detail_count
        self.fail_insert=fail_insert; self.sql=[]; self.commits=0; self.rollbacks=0; self.closed=0
    def cursor(self): return Cursor(self)
    def commit(self): self.commits+=1
    def rollback(self): self.rollbacks+=1
    def close(self): self.closed+=1


def call(b=None, c=None, ev=None, approval=True):
    return write_approved_batch(b or batch(),explicit_db_write_approval=approval,
        evidence_by_gid=evidence() if ev is None else ev, connection_factory=lambda:c)


def test_explicit_consent_blocks_without_db_access():
    with pytest.raises(ProductionBlocked, match='EXPLICIT_DB_WRITE_APPROVAL_REQUIRED'):
        call(c=None, approval=False)


def test_success_transaction_and_fields():
    c=Connection()
    out=call(c=c)
    assert out['run_id']==12 and out['candidate_count']==1 and out['evidence_count']==1
    assert (c.commits,c.rollbacks,c.closed)==(1,0,1)
    assert sum('INSERT INTO priority_candidate ' in s for s,_ in c.sql)==1
    assert any(
        'INSERT INTO priority_candidate ' in sql
        and isinstance(args[-1], str) and args[-1].startswith('ev1:')
        for sql, args in c.sql
    )


def test_setting_not_approved_rolls_back():
    c=Connection(status='PENDING')
    with pytest.raises(ProductionBlocked,match='SETTING_NOT_APPROVED'): call(c=c)
    assert (c.commits,c.rollbacks,c.closed)==(0,1,1)


def test_bad_candidate_blocked_without_db_access():
    b=batch()
    b=replace(b, candidates=({**b.candidates[0], 'input_status':'EXPLORATORY_PROXY'},))
    with pytest.raises(ProductionBlocked,match='UNVERIFIED_COMPLAINT_INPUT'):
        call(b=b,c=None)


def test_evidence_failure_rolls_back_entire_run():
    c=Connection(fail_insert=True)
    with pytest.raises(RuntimeError,match='simulated'): call(c=c)
    assert (c.commits,c.rollbacks,c.closed)==(0,1,1)


def test_candidate_count_mismatch_rolls_back():
    c=Connection(count=0)
    with pytest.raises(ProductionBlocked, match='SAVED_ROW_COUNT_MISMATCH'): call(c=c)
    assert (c.commits,c.rollbacks,c.closed)==(0,1,1)


def test_detail_count_mismatch_rolls_back():
    c=Connection(detail_count=0)
    with pytest.raises(ProductionBlocked, match='DETAIL_POINTER_COUNT_MISMATCH'): call(c=c)
    assert (c.commits,c.rollbacks,c.closed)==(0,1,1)


def test_missing_evidence_blocked_before_db():
    with pytest.raises(ProductionBlocked,match='DETAIL_EVIDENCE_REQUIRED'):
        write_approved_batch(batch(), explicit_db_write_approval=True,
                             connection_factory=lambda:1/0)


def test_partial_evidence_blocked_before_db():
    with pytest.raises(ProductionBlocked,match='DETAIL_GRID_SET_MISMATCH'):
        call(c=None,ev={})


def test_missing_detail_field_blocked_before_db():
    ev=evidence(); del ev['g1']['confidence_grade']
    with pytest.raises(ProductionBlocked, match='DETAIL_EIGHT_FIELDS_REQUIRED'):
        call(c=None,ev=ev)


def test_fingerprint_changes_with_result_and_evidence():
    first=call(c=Connection())
    b=batch(); changed=replace(b,candidates=({**b.candidates[0],'official_score':'73'},))
    second=call(b=changed,c=Connection())
    ev=evidence();ev['g1']['domain_scores']['hazard']=73
    third=call(c=Connection(),ev=ev)
    assert len({first['fingerprint'],second['fingerprint'],third['fingerprint']})==3


# EIGHT_FIELD_CONTRACT_FIXTURE: keep the original sample but include required evidence.
_original_five_field_evidence = evidence
def evidence_8field_fixture():
    result = _original_five_field_evidence()
    for detail in result.values():
        detail.setdefault('exclusion_reasons', [])
        detail.setdefault('complaint_contribution', 0)
        detail.setdefault('policy_version', 'v1')
    return result
evidence = evidence_8field_fixture
