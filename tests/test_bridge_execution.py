import pandas as pd
import pytest
from app.services.scoring.bridge_execution import preview_with_unverified_complaints
from app.services.scoring.calculation import FEATURES


def grid():
    d = {'ID_gid': ['g1', 'g2'], 'id_gu': ['구A', '구B'],
         'ext_survey_scope_obstacle': ['Y', 'Y']}
    d.update({k: [1., 2.] for k in FEATURES})
    return pd.DataFrame(d)


def config():
    return {
        'policy': {'label': 'experimental-only', 'normalization': 'positive_upper',
                   'observation': 'record_zero_counterfactual', 'domain_weights':
                   {'accident': .25, 'hazard': .25, 'exposure': .25, 'vulnerability': .25},
                   'accident_reduce': 'mean', 'missing': 'renormalize'},
        'comparison_population': 'hazard_observed',
        'fit_population': 'all_input_positive_counts',
        'complaint_mode': 'bonus', 'coefficient_points': 5,
    }


def source():
    return pd.DataFrame([
        dict(complaint_id='1', gid='g1', relevance='보행안전 관련', class_confidence=.8, coord_accuracy='높음', dup_flag=None),
        dict(complaint_id='2', gid='g2', relevance=None, class_confidence=None, coord_accuracy='높음', dup_flag=None),
    ])


def test_preview_never_issues_official_ranks_even_with_related_label():
    out = preview_with_unverified_complaints(grid(), source(), config())
    assert out['complaint_bridge']['preview_counts'][0]['preview_related_count'] == 1
    assert out['complaint_bridge']['eligible_for_official'] is False
    assert out['official_score_generated'] is False
    assert all(r['score'] is None and r['rank_no'] is None for r in out['rows'])
    assert all(r['base_score'] is not None for r in out['rows'])
    assert 'CLASSIFIED_AGGREGATE_NOT_SUPPLIED' in out['official_blockers']


def test_unauthorized_label_rejected_before_calculation():
    s = source(); s.loc[0, 'relevance'] = '관련'
    with pytest.raises(ValueError, match='BRIDGE_UNKNOWN_CLASSIFICATION_VOCABULARY'):
        preview_with_unverified_complaints(grid(), s, config())


def test_unknown_grid_rejected_before_calculation():
    s = source(); s.loc[0, 'gid'] = 'unknown'
    with pytest.raises(ValueError, match='BRIDGE_UNKNOWN_GRID_REFERENCE'):
        preview_with_unverified_complaints(grid(), s, config())


def test_duplicate_source_rejected():
    s = source(); s.loc[1, 'complaint_id'] = '1'
    with pytest.raises(ValueError, match='BRIDGE_INVALID_COMPLAINT_IDS'):
        preview_with_unverified_complaints(grid(), s, config())
