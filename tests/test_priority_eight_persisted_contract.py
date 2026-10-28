"""Current 78.note sidecar contract regression; no operational DB writes."""
import hashlib
import json
from decimal import Decimal

import pytest

from app.services.priority.details import (
    FIELDS, LEGACY_FIELDS, encode_evidence, read_evidence, store_evidence,
)
from app.services.scoring.mysql_writer import _validate_evidence
from app.services.scoring.production_writer import OfficialBatch, ProductionBlocked


def eight():
    return {
        'domain_scores': {'hazard': 42.0, 'accident': None},
        'indicator_contributions': {'feature_1': 4.25},
        'unevaluated_reasons': {'accident': 'MISSING_INPUT'},
        'confidence_grade': 'UNVERIFIED',
        'score_excluding_accidents': Decimal('52.125'),
        'exclusion_reasons': [],
        'complaint_contribution': -2.0,
        'policy_version': 'POLICY_V1',
    }


def batch():
    return OfficialBatch(
        build_id='b', rule_version='POLICY_V1', setting_version_id=2,
        setting_content_ref='sha256:' + 'a'*64,
        input_digest='b'*64, policy_digest='a'*64,
        complaint_contract_digest='c'*64,
        candidates=({'gid':'g1', 'official_score':50, 'rank_no':1,
                     'complaint_cnt':0, 'complaint_cnt_excl_low':0,
                     'calculation_status':'OFFICIAL', 'input_status':'VERIFIED_CLASSIFIED',
                     'classification_status':'COMPLETE'},),
        authorized_by='external-approver', approval_reference='external-record')


def test_eight_roundtrip_uses_78_note_and_preserves_negative_contribution(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    detail = eight()
    assert len(FIELDS) == 8
    note = store_evidence(7, 'g1', detail)
    assert note.startswith('ev1:') and len(note) == 68
    result = read_evidence(lambda _sql,_args:[{'note':note}], 7, 'g1')
    assert result['stored'] is True and result['evidence_version'] == 'EIGHT'
    assert set(FIELDS) <= result.keys()
    assert result['complaint_contribution'] == -2.0
    assert result['policy_version'] == 'POLICY_V1'


def test_legacy_five_read_compatible(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    legacy = {k:eight()[k] for k in LEGACY_FIELDS}
    note = store_evidence(8,'old',legacy)
    value = read_evidence(lambda _sql,_args:[{'note':note}],8,'old')
    assert value['evidence_version'] == 'LEGACY_FIVE'
    assert all(value[k] is None for k in FIELDS[5:])


def test_tamper_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    note=store_evidence(7,'g1',eight())
    digest=note[4:]
    location=tmp_path/digest[:2]/(digest+'.json')
    location.write_bytes(location.read_bytes() + b' ')
    with pytest.raises(ValueError,match='checksum'):
        read_evidence(lambda _sql,_args:[{'note':note}],7,'g1')


def test_writer_rejects_missing_eighth_item_and_wrong_version():
    ev=eight()
    del ev['complaint_contribution']
    with pytest.raises(ProductionBlocked,match='DETAIL_EIGHT_FIELDS_REQUIRED'):
        _validate_evidence(batch(), {'g1':ev})
    ev=eight();ev['policy_version']='OTHER'
    with pytest.raises(ProductionBlocked,match='DETAIL_POLICY_VERSION_MISMATCH'):
        _validate_evidence(batch(), {'g1':ev})


def test_missing_pointer_is_not_counted_as_verified():
    result=read_evidence(lambda _sql,_args:[{'note':None}],7,'g1')
    assert result['stored'] is False
    assert all(result[k] is None for k in FIELDS)


def test_bad_values_blocked_before_save():
    d=eight();d['score_excluding_accidents']=120
    with pytest.raises(ValueError,match='accident'):
        encode_evidence(7,'g1',d)
    d=eight();d['complaint_contribution']=float('nan')
    with pytest.raises(ValueError,match='complaint'):
        encode_evidence(7,'g1',d)
