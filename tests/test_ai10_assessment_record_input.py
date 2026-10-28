"""이 파일만 독립 실행 시에도 검증 가능. 전역 import 후킹 없음."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def module(monkeypatch):
    # 운영 모듈은 변경하지 않고, 외부 의존 경계만 지역적으로 교체한다.
    parent = 'app.services.AI-10'
    for name in ('app', 'app.services', parent):
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'app' / 'services' / 'AI-10')] if name == parent else []
            monkeypatch.setitem(sys.modules, name, pkg)
    bridge_name = parent + '.ai10_assessment_evidence_bridge'
    fake_bridge = types.ModuleType(bridge_name)
    def stub_bridge(**kw):
        if not kw['source_confirmation'] or kw['source_id'] != 'SRC24':
            raise ValueError('연결 근거 확인 실패')
        return {'evidence': {'source_table': kw['table'], 'source_column': kw['field'],
                             'record_reference': kw['record_key'], 'source_id': kw['source_id'],
                             'evidence_state': kw['evidence_state'], 'claim_or_finding': '확인 필요한 판정값'},
                'source_confirmation': kw['source_confirmation']}
    fake_bridge.build_assessment_evidence = stub_bridge
    monkeypatch.setitem(sys.modules, bridge_name, fake_bridge)
    draft_name = parent + '.ai10_case_draft'
    fake_draft = types.ModuleType(draft_name)
    class EvidenceItem:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    class CaseInput:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    fake_draft.EvidenceItem = EvidenceItem
    fake_draft.CaseInput = CaseInput
    monkeypatch.setitem(sys.modules, draft_name, fake_draft)
    return importlib.import_module(parent + '.ai10_assessment_record_input')


def params():
    return dict(case_reference='AI10-TEST', issue_description='현장 확인이 필요한 시설 상태',
        table='assess_zone', facility_id='Z100',
        rows=[{'zone_id': 'Z100', 'status_test': 'Y'}],
        attestations=[dict(field='status_test', source_id='SRC24',
                           evidence_state='estimated_or_derived', source_confirmation='verified-link-001')],
        source_rows=[{'source_id':'SRC24'}])


def test_verified_connection_is_value_free(module):
    result = module.build_case_from_assessment(**params())
    assert result['case'].facility_id == 'Z100'
    assert result['case'].evidence_items[0].source_id == 'SRC24'
    assert not hasattr(result['case'].evidence_items[0], 'raw_value')
    assert not result['llm_invoked'] and not result['db_written']


def test_no_attestation_blocks(module):
    p = params(); p['attestations'] = []
    with pytest.raises(ValueError): module.build_case_from_assessment(**p)


def test_ambiguous_id_blocks(module):
    p = params(); p['rows'] *= 2
    with pytest.raises(ValueError): module.build_case_from_assessment(**p)


def test_unknown_provenance_blocks(module):
    p = params(); p['attestations'][0]['source_id'] = 'SRC53'
    with pytest.raises(ValueError): module.build_case_from_assessment(**p)


def test_missing_column_value_blocks(module):
    p = params(); p['rows'][0].pop('status_test')
    with pytest.raises(ValueError): module.build_case_from_assessment(**p)
