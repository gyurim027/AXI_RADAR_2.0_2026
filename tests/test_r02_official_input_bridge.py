from datetime import date
import pytest
from app.services.scoring.r02_official_input_bridge import prepare_r02_official_input
from app.services.scoring.approved_inputs import InputBlocked

BASE={'received_date':'2026-09-01','gid':'G1','class_method':'AI',
      'relevance':'보행안전 관련','ped_type':'장애물','low_confidence':False}
def r(cid,**updates):return {**BASE,'complaint_id':cid,**updates}

def test_eligible_aggregation_and_exclusions():
    result=prepare_r02_official_input([r('a'),r('b',relevance='불명'),r('c',relevance='비관련')],
        gids={'G1','G2'},start=date(2021,1,1),end=date(2026,9,30),explicit_exclusion_policy=True)
    assert result.audit['source_rows']==3
    assert result.audit['eligible_rows']==2
    assert result.audit['excluded_rows']==1
    assert result.audit['excluded_reasons']=={'UNRESOLVED_CLASSIFICATION':1}
    assert result.audit['approved_for_official_write'] is False
    assert len(result.counts_by_gid)==2
    assert all(x['classification_status']=='COMPLETE' for x in result.counts_by_gid)
    by_gid={x['gid']:x for x in result.counts_by_gid}
    assert by_gid['G1']['relevant_count']==1
    assert by_gid['G2']['relevant_count']==0

def test_policy_gate_closed():
    with pytest.raises(InputBlocked,match='EXPLICIT_SELECTION_REQUIRED'):
        prepare_r02_official_input([r('a')],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30))

def test_unmapped_still_blocked():
    with pytest.raises(InputBlocked,match='UNMAPPED_REQUIRES_SEPARATE_POLICY'):
        prepare_r02_official_input([r('a',gid='G9')],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30),explicit_exclusion_policy=True)

def test_period_fails_closed():
    with pytest.raises(InputBlocked,match='SOURCE_PERIOD_MISMATCH'):
        prepare_r02_official_input([r('a',received_date='2020-12-31')],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30),explicit_exclusion_policy=True)

def test_duplicate_fails_closed():
    with pytest.raises(InputBlocked,match='DUPLICATE'):
        prepare_r02_official_input([r('a'),r('a')],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30),explicit_exclusion_policy=True)

def test_related_type_missing_excluded_not_negative():
    p=prepare_r02_official_input([r('a',ped_type=None)],gids={'G1'},start=date(2021,1,1),end=date(2026,9,30),explicit_exclusion_policy=True)
    assert p.audit['excluded_reasons']=={'RELATED_TYPE_MISSING':1}
    assert p.counts_by_gid[0]['classification_status']=='COMPLETE'
    assert p.counts_by_gid[0]['relevant_count']==0
