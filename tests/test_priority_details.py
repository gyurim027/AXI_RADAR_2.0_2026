"""Current 78.note content-addressed evidence contract (legacy 5 and current 8).

This supersedes a SQL-table test for the removed priority_candidate_detail writer.
"""
import hashlib
import json
from decimal import Decimal

import pytest
from app.services.priority.details import (
    FIELDS, LEGACY_FIELDS, encode_evidence, read_evidence, store_evidence,
)


def sample(eight=False):
    base = dict(
        domain_scores={'hazard': 35},
        indicator_contributions={'fatal': 8},
        unevaluated_reasons=['unobserved'],
        confidence_grade='UNVERIFIED',
        score_excluding_accidents=Decimal('32.5'),
    )
    if eight:
        base.update(exclusion_reasons=[], complaint_contribution=Decimal('0.75'),
                    policy_version='DEMO-NOT-APPROVED')
    return base


def read_stub(note):
    return lambda sql, args: [{'note': note}]


def test_roundtrip_legacy_and_eight(tmp_path, monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    for is_eight in (False, True):
        note = store_evidence(7, 'g1', sample(is_eight))
        assert note.startswith('ev1:') and len(note) == 68
        obj = read_evidence(read_stub(note), 7, 'g1')
        assert obj['stored'] is True
        assert obj['evidence_version'] == ('EIGHT' if is_eight else 'LEGACY_FIVE')
        assert obj['domain_scores'] == {'hazard': 35}
        assert obj['score_excluding_accidents'] == '32.5'
        assert set(FIELDS).issubset(obj)
        if is_eight:
            assert obj['complaint_contribution'] == '0.75'
        else:
            assert obj['complaint_contribution'] is None


def test_checksum_tampering_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    note = store_evidence(7, 'g1', sample(True))
    filename = tmp_path / note[4:6] / (note[4:] + '.json')
    filename.write_bytes(filename.read_bytes().replace(b'35', b'36'))
    with pytest.raises(ValueError, match='checksum'):
        read_evidence(read_stub(note), 7, 'g1')


def test_wrong_identity_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    note = store_evidence(7, 'g1', sample(True))
    with pytest.raises(ValueError, match='identity'):
        read_evidence(read_stub(note), 8, 'g1')


def test_missing_candidate_fails_closed():
    with pytest.raises(ValueError, match='identity'):
        read_evidence(lambda sql, args: [], 7, 'g1')


def test_candidate_without_pointer_returns_unstored():
    got = read_evidence(read_stub('manual note'), 7, 'g1')
    assert got['stored'] is False
    assert all(got[k] is None for k in FIELDS)


def test_invalid_partial_fields_rejected():
    with pytest.raises(ValueError, match='detail fields'):
        encode_evidence(7, 'g1', {'confidence_grade': 'A'})


def test_invalid_score_rejected():
    d = sample(True)
    d['score_excluding_accidents'] = 101
    with pytest.raises(ValueError, match='accident'):
        encode_evidence(7, 'g1', d)


@pytest.mark.parametrize('value', ['35', True, -1, 101, float('nan')])
def test_invalid_numeric_rejected(value):
    d = sample(True)
    d['domain_scores']['hazard'] = value
    with pytest.raises(ValueError, match='numeric'):
        encode_evidence(7, 'g1', d)


def test_duplicate_keys_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    note = store_evidence(7, 'g1', sample(True))
    raw = (tmp_path / note[4:6] / (note[4:] + '.json')).read_bytes()
    obj = raw.decode('utf-8').replace('"gid":"g1"', '"gid":"g1","gid":"g1"')
    changed = obj.encode('utf-8')
    digest = hashlib.sha256(changed).hexdigest()
    path = tmp_path / digest[:2] / (digest + '.json')
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(changed)
    with pytest.raises(ValueError, match='duplicate'):
        read_evidence(read_stub('ev1:' + digest), 7, 'g1')


def test_rewritten_json_with_same_data_is_not_same_hash(tmp_path, monkeypatch):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    note = store_evidence(7, 'g1', sample(True))
    raw = (tmp_path / note[4:6] / (note[4:] + '.json')).read_bytes()
    reformatted = json.dumps(json.loads(raw), indent=2).encode('utf-8')
    (tmp_path / note[4:6] / (note[4:] + '.json')).write_bytes(reformatted)
    with pytest.raises(ValueError, match='checksum'):
        read_evidence(read_stub(note), 7, 'g1')
