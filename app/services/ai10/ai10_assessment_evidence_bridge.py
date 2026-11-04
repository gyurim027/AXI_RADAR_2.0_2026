"""AI-10 판정 근거 입력 연결: 검증된 명시적 출처만 수용한다.

이 모듈은 DB를 수정하거나 모델을 호출하지 않는다. DB 56의 used_tables로 SRC를
역추정하지 않으며, 판정값/원본/개인정보의 외부 반출 허가는 별도 검증 대상이다.
"""
from __future__ import annotations

import importlib
from typing import Any, Mapping

TABLES = frozenset({'assess_crosswalk', 'assess_sidewalk', 'assess_intersection', 'assess_zone'})


def build_assessment_evidence(
    *,
    table: str,
    row: Mapping[str, Any],
    field: str,
    record_key: str,
    source_id: str,
    evidence_state: str,
    source_rows: list[dict[str, Any]],
    source_confirmation: str,
) -> dict[str, Any]:
    """명시적으로 검증된 판정값 하나를 EvidenceItem용 dict로 바꾼다.

    source_confirmation: 출처를 확인한 파일/쿼리/작업 근거의 식별자.
    이 입력은 *연결 근거를 보존*할 뿐 해당 근거의 사실성은 자동 인증하지 않는다.
    """
    if table not in TABLES:
        raise ValueError('지원하지 않는 판정 테이블')
    if not isinstance(row, Mapping) or not field or field not in row:
        raise ValueError('판정 행 또는 컬럼을 확인할 수 없음')
    if not isinstance(record_key, str) or not record_key.strip():
        raise ValueError('원래 판정 레코드의 식별자 필요')
    if not isinstance(source_confirmation, str) or not source_confirmation.strip():
        raise ValueError('컬럼-SRC 연결 근거 미확인')
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError('명시적 SRC 번호 필요')
    if not isinstance(source_rows, list):
        raise TypeError('DB 56 조회 결과가 필요')
    prov = importlib.import_module('app.services.ai10.ai10_source_provenance')
    item = {
        'source_table': table,
        'source_column': field,
        'record_reference': record_key.strip(),
        'source_id': source_id,
        'evidence_state': evidence_state,
        # 좌표, 도형, 원본 값은 자동 프롬프트 입력에 복사하지 않는다.
        'claim_or_finding': f'{field}: 판정 기록값 확인 (실제 값은 검증된 별도 입력에서 제공)',
    }
    audit = prov.audit_evidence_sources([item], source_rows)
    if source_id not in audit['catalog_matched_ids'] or any(
        issue.get('status') in {'source_id_missing', 'invalid_source_id', 'not_in_source_list'}
        for issue in audit['issues']
    ):
        raise ValueError('DB 56 목록에서 SRC 확인 불가')
    return {
        'evidence': item,
        'value_included_in_prompt': False,
        'source_confirmation': source_confirmation.strip(),
        'source_audit': audit,
        'external_transfer_approved': False,
    }
