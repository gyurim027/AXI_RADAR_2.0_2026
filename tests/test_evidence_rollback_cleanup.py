from pathlib import Path
import pytest
from app.services.priority.details import store_evidence, cleanup_uncommitted_evidence


def _evidence():
    return {'domain_scores': {'hazard': 72},
            'indicator_contributions': {'indicator_1': 12.5},
            'unevaluated_reasons': [], 'confidence_grade': 'UNVERIFIED',
            'score_excluding_accidents': 60,
            'exclusion_reasons': [], 'complaint_contribution': 0,
            'policy_version': 'v1'}


def test_rollback_removes_only_created_files(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    created = []
    pointer = store_evidence(1, 'a', _evidence(), on_created=lambda path, digest: created.append((path, digest)))
    assert pointer.startswith('ev1:') and len(created) == 1
    path = created[0][0]
    assert path.exists()
    cleanup_uncommitted_evidence(created)
    assert not path.exists()


def test_preexisting_evidence_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    created = []
    store_evidence(1, 'a', _evidence(), on_created=lambda path, digest: created.append((path, digest)))
    assert len(created) == 1
    retry_created = []
    store_evidence(1, 'a', _evidence(), on_created=lambda path, digest: retry_created.append((path, digest)))
    assert retry_created == []
    cleanup_uncommitted_evidence(retry_created)
    assert created[0][0].exists()


def test_changed_content_not_deleted(monkeypatch, tmp_path):
    monkeypatch.setenv('RADAR_PRIORITY_EVIDENCE_DIR', str(tmp_path))
    created = []
    store_evidence(1, 'a', _evidence(), on_created=lambda path, digest: created.append((path, digest)))
    created[0][0].write_text('unexpected change', encoding='utf8')
    cleanup_uncommitted_evidence(created)
    assert created[0][0].exists()
