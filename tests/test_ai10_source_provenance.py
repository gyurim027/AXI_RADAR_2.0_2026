import importlib.util
from pathlib import Path
m_path = Path(__file__).resolve().parents[1] / 'app/services/AI-10/ai10_source_provenance.py'
spec = importlib.util.spec_from_file_location('ai10_source_provenance', m_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_missing_not_guessed():
    result = m.audit_evidence_sources([{'source_table':'assess_sidewalk','source_column':'width_m_raw'}], [{'source_id':'SRC18','access_level':'제한'}])
    assert result['catalog_matched_ids'] == []
    assert result['issues'][0]['status'] == 'source_id_missing'
    assert result['external_transfer_approved'] is False

def test_explicit_id_catalog_only():
    result = m.audit_evidence_sources([{'source_id':'SRC06'}], [{'source_id':'SRC06','access_level':'공개'}])
    assert result['catalog_matched_ids'] == ['SRC06']
    assert result['provenance_verified'] is False

def test_no_raw_or_internal_leak():
    result = m.audit_evidence_sources([{'source_id':'SRC53','raw_value':'private'}], [{'source_id':'SRC53','access_level':'내부'}])
    assert result['issues'][0]['status'] == 'external_review_required'
    assert 'private' not in str(result)
