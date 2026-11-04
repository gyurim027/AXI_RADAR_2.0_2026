import json
from hashlib import sha256
from pathlib import Path
import pandas as pd
import pytest
from app.services.scoring.execution import prepare, audit_source, resolve_setting
from app.services.scoring.calculation import FEATURES


def config():
    return json.loads(Path('docs/scoring/bonus.json').read_text())


def frame():
    return pd.DataFrame([{**{k:1 for k in FEATURES}, 'ID_gid': 'g1', 'id_gu':'성남시 분당구', 'ext_survey_scope_obstacle':'Y'}])


def test_missing_classification_preserves_base_but_blocks_final():
    src=pd.DataFrame([{'complaint_id':'c1','gid':'g1','relevance':None,'class_confidence':None}])
    result=prepare(frame(),config(),source=src)
    row=result['rows'][0]
    assert row['base_score']==100
    assert row['score'] is None and row['rank_no'] is None and row['complaint_cnt'] is None
    assert row['details']['confidence_grade'] is None
    assert row['accident_exclusion_comparison']['fixed_denominator']==75
    assert row['accident_exclusion_comparison']['redistributed_denominator']==100
    assert 'SOURCE_CLASSIFICATION_PENDING' in result['official_blockers']


def test_producer_vocabulary_and_unknown_confidence():
    src=pd.DataFrame([{'complaint_id':str(i),'gid':None,'relevance':r,'class_confidence':1.0}
                     for i,r in enumerate(['보행안전 관련','비관련','불명','관련'])])
    out=audit_source(src)
    assert (out['related_labeled'],out['not_related_labeled'],out['pending_classification'])==(1,1,2)
    assert out['grid_unassigned']==4 and not out['official_eligible']


def test_exact_selected_content_bytes_not_approval_only():
    content=json.dumps(config()).encode()
    row={'setting_version_id':3,'content_ref':'sha256:'+sha256(content).hexdigest(),
         'version_label':config()['policy']['label'],'approval_status':'승인'}
    _,bound=resolve_setting(content,row)
    assert bound['official_policy_verified'] is False
    with pytest.raises(ValueError,match='HASH'):
        resolve_setting(content+b' ',row)


def test_scope_aware_absence_is_not_zero():
    f=frame();f['cond_obstacle_cnt']=0;f['ext_survey_scope_obstacle']='N'
    out=prepare(f,config())['rows'][0]
    assert out['details']['unevaluated_reasons']['indicators']['cond_obstacle_cnt']=='OUTSIDE_SURVEY_SCOPE'
    assert out['observed_indicator_count']==8
