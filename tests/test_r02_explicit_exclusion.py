from app.services.scoring.r02_explicit_exclusion import partition_explicitly
from app.services.scoring.approved_inputs import InputBlocked
import pytest

BASE = {'received_date':'2026-09-01', 'gid':'G1', 'class_method':'AI',
        'relevance':'보행안전 관련', 'ped_type':'장애물'}

def row(cid, **changes):
    return {**BASE, 'complaint_id':cid, **changes}

def test_gate_requires_explicit_selection():
    with pytest.raises(InputBlocked, match='EXPLICIT_SELECTION_REQUIRED'):
        partition_explicitly([row('1')], {'G1'})

def test_unresolved_excluded_not_rewritten_negative():
    p = partition_explicitly([row('1',relevance='불명'), row('2',relevance='비관련')],{'G1'},explicit_policy=True)
    assert p.counts['excluded'] == 1
    assert p.excluded[0]['reason']=='UNRESOLVED_CLASSIFICATION'
    assert p.eligible[0]['relevance']=='비관련'

def test_unmapped_is_not_silently_excluded():
    with pytest.raises(InputBlocked,match='UNMAPPED_REQUIRES_SEPARATE_POLICY'):
        partition_explicitly([row('1',gid='G2')],{'G1'},explicit_policy=True)

def test_missing_type_is_explicitly_excluded():
    p = partition_explicitly([row('2',ped_type=None)],{'G1'},explicit_policy=True)
    assert p.counts['RELATED_TYPE_MISSING']==1

def test_duplicate_rejected():
    with pytest.raises(InputBlocked,match='DUPLICATE'):
        partition_explicitly([row('1'),row('1')],{'G1'},explicit_policy=True)
