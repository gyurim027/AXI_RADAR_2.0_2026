from datetime import date
import pytest
from app.services.scoring.approved_inputs import InputBlocked
from app.services.scoring.r02_full_source_quarantine import prepare_full_source_r02,UNMAPPED_POLICY_ID
BASE={'received_date':'2026-09-01','gid':'G1','class_method':'AI','relevance':'보행안전 관련','ped_type':'장애물','low_confidence':False}
def row(cid,**kw):return {**BASE,'complaint_id':cid,**kw}
def go(rows,**kw):return prepare_full_source_r02(rows,gids={'G1','G2'},start=date(2021,1,1),end=date(2026,9,30),mapped_exclusion_policy=True,unmapped_quarantine_policy=True,**kw)
def test_full_accounting_three_buckets():
    f=go([row('1'),row('2',relevance='불명'),row('3',gid=None),row('4',gid=None,relevance='불명'),row('5',relevance='비관련')])
    a=f.audit
    assert (a['source_rows'],a['mapped_rows'],a['mapped_eligible_rows'],a['mapped_excluded_rows'],a['unmapped_quarantined_rows'])==(5,3,2,1,2)
    assert a['unmapped_quarantine_reasons']=={'RELATED_WITH_TYPE':1,'UNRESOLVED':1}
    assert a['grid_count']==2 and a['prepared_grid_count']==2
    assert not a['approved_for_official_write']
def test_both_policy_gates_required():
    with pytest.raises(InputBlocked,match='BOTH_POLICIES'):
        prepare_full_source_r02([row('1')],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30),mapped_exclusion_policy=True)
def test_nonnull_unknown_grid_is_blocked():
    with pytest.raises(InputBlocked,match='UNKNOWN_NONNULL_GID'):
        go([row('1',gid='alien')])
def test_duplicate_blocked_across_populations():
    with pytest.raises(InputBlocked,match='DUPLICATE'):
        go([row('1'),row('1',gid=None)])
def test_quarantine_cannot_become_negative():
    a=go([row('1',gid=None)]).audit
    assert a['mapped_eligible_nonrelated']==0 and a['unmapped_quarantine_reasons']['RELATED_WITH_TYPE']==1
def test_digest_order_independent():
    rs=[row('1',gid=None),row('2',gid=None,relevance='불명'),row('3')]
    a=go(rs).audit;b=go(list(reversed(rs))).audit
    assert a['audit_sha256']==b['audit_sha256']
def test_period_blocked():
    with pytest.raises(InputBlocked,match='SOURCE_PERIOD_MISMATCH'):
        go([row('1',received_date='2020-12-31')])
