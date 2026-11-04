import pandas as pd
import pytest
from app.services.scoring.complaint_bridge import inspect_classified_source


def sample():
    return pd.DataFrame([
        dict(complaint_id='1',gid='g1',relevance='보행안전 관련',class_confidence=.85,coord_accuracy='높음',dup_flag=None),
        dict(complaint_id='2',gid='g1',relevance='불명',class_confidence=.8,coord_accuracy='높음',dup_flag=None),
        dict(complaint_id='3',gid='g2',relevance=None,class_confidence=None,coord_accuracy='높음',dup_flag=None),
        dict(complaint_id='4',gid='g2',relevance='보행안전 관련',class_confidence=.95,coord_accuracy='낮음',dup_flag=None),
        dict(complaint_id='5',gid='g2',relevance='비관련',class_confidence=.9,coord_accuracy='높음',dup_flag=None),
    ])


def test_preview_does_not_convert_pending_into_verified_zero():
    got=inspect_classified_source(sample(),['g1','g2'])
    assert got.preview.preview_related_count.tolist()==[1,0]
    assert got.inventory['pending_or_unknown']==2
    assert 'SOURCE_CLASSIFICATION_PENDING' in got.inventory['official_blockers']
    assert not got.eligible_for_official


def test_rejects_foreign_grid():
    frame=sample();frame.loc[0,'gid']='external'
    with pytest.raises(ValueError,match='BRIDGE_UNKNOWN_GRID_REFERENCE'):
        inspect_classified_source(frame,['g1','g2'])


def test_rejects_bad_vocab():
    frame=sample();frame.loc[0,'relevance']='관련'
    with pytest.raises(ValueError,match='BRIDGE_UNKNOWN_CLASSIFICATION_VOCABULARY'):
        inspect_classified_source(frame,['g1','g2'])


def test_rejects_bad_confidence():
    frame=sample();frame.loc[0,'class_confidence']=1.2
    with pytest.raises(ValueError,match='BRIDGE_INVALID_CONFIDENCE'):
        inspect_classified_source(frame,['g1','g2'])


def test_rejects_duplicate_ids():
    frame=sample();frame.loc[1,'complaint_id']='1'
    with pytest.raises(ValueError,match='BRIDGE_INVALID_COMPLAINT_IDS'):
        inspect_classified_source(frame,['g1','g2'])


def test_flags_duplicate():
    frame=sample();frame.loc[0,'dup_flag']='Y'
    got=inspect_classified_source(frame,['g1','g2'])
    assert got.preview.preview_related_count.sum()==0
    assert got.inventory['related_excluded_flagged_duplicate']==1
