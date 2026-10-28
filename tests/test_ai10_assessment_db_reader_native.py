"""테스트는 DB 접근 없이, 실제 테이블·컬럼명과 SQL 가드를 점검한다."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

SRC = Path(__file__).resolve().parents[1] / 'app/services/AI-10/ai10_assessment_db_reader.py'
spec = importlib.util.spec_from_file_location('ai10_native_db_reader', SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _attest(field):
    return [{'field': field, 'source_id': 'SRC18',
             'evidence_state': 'derived', 'source_confirmation': 'reviewed'}]


@pytest.mark.parametrize(('table', 'pk'), list(module.TABLE_KEYS.items()))
def test_v23_actual_primary_keys(table, pk):
    statements = []
    def read(sql, args=()):
        statements.append((sql, args))
        if 'information_schema' in sql:
            return [{'COLUMN_NAME': pk}, {'COLUMN_NAME': '테스트한글컬럼'}]
        if 'source_list' in sql:
            return [{'source_id': 'SRC18'}]
        return [{pk: 'ID001', '테스트한글컬럼': 'Y'}]
    with patch.object(module.importlib, 'import_module') as loader:
        loader.return_value.build_case_from_assessment.return_value = {'llm_invoked': False}
        result = module.load_assessment_case_from_db(
            case_reference='A1', issue_description='현장 확인 필요',
            table=table, facility_id='ID001', attestations=_attest('테스트한글컬럼'),
            read_only=read)
    assert result['llm_invoked'] is False
    assert f'`{pk}` = %s LIMIT 2' in statements[1][0]
    assert '`테스트한글컬럼`' in statements[1][0]


def test_nonexistent_column_rejected():
    calls = []
    def read(sql, args=()):
        calls.append(sql)
        return [{'COLUMN_NAME': 'UFID'}]
    with pytest.raises(ValueError):
        module.load_assessment_case_from_db(
            case_reference='A1', issue_description='현장 확인 필요',
            table='assess_sidewalk', facility_id='ID001',
            attestations=_attest('없는컬럼'), read_only=read)
    assert len(calls) == 1


@pytest.mark.parametrize('field', ['x`', 'x.y', 'x\nY'])
def test_unsafe_names_blocked_before_query(field):
    def not_called(*args, **kwargs):
        raise AssertionError('DB 조회하면 안 됨')
    with pytest.raises(ValueError):
        module.load_assessment_case_from_db(
            case_reference='A1', issue_description='현장 확인 필요',
            table='assess_sidewalk', facility_id='ID001',
            attestations=_attest(field), read_only=not_called)
