"""v2.3 MySQL 판정행 읽기 전용 조회. DB의 실제 컬럼명을 변경 없이 사용.

주의: source_id 검증은 출처 일치/외부 전송 허가를 의미하지 않음.
"""
from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any, Callable

# v2.3 DDL에서 확인한 실제 PK 컬럼(번역·별칭 처리하지 않음).
TABLE_KEYS = {
    'assess_crosswalk': 'crosswalk_mgmt_no',
    'assess_sidewalk': 'UFID',
    'assess_intersection': 'intersection_id',
    'assess_zone': 'zone_id',
}


def _safe_column_name(value: Any) -> bool:
    """한글/영문을 구별하지 않고 실제 DB 명칭을 허용; SQL 제어문자 차단."""
    return (isinstance(value, str) and bool(value.strip()) and value == value.strip()
            and '`' not in value and '.' not in value
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


def load_assessment_case_from_db(
    *, case_reference: str, issue_description: str,
    table: str, facility_id: str,
    attestations: Sequence[Mapping[str, str]],
    ck_reference: str | None = None,
    read_only: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """검증 근거가 명시된 컬럼만 조회하고 기존 CaseInput 변환 함수에 전달.

    AI 호출/DB 저장 없음. attestations는 field, source_id, evidence_state,
    source_confirmation을 포함해야 하며 확인된 출처만 호출자가 입력해야 함.
    """
    if table not in TABLE_KEYS:
        raise ValueError('지원하지 않는 판정 테이블')
    if not isinstance(facility_id, str) or not facility_id.strip():
        raise ValueError('시설 식별자 누락')
    if not isinstance(case_reference, str) or not case_reference.strip():
        raise ValueError('사례 식별자 누락')
    if not isinstance(issue_description, str) or not issue_description.strip():
        raise ValueError('문제 설명 누락')
    if not attestations:
        raise ValueError('출처 확인 근거 미제공')

    key = TABLE_KEYS[table]
    fields: list[str] = []
    for attestation in attestations:
        if not isinstance(attestation, Mapping):
            raise ValueError('출처 연결 형식 오류')
        field = attestation.get('field')
        if not _safe_column_name(field) or field == key or field in fields:
            raise ValueError('컬럼 식별자 오류·중복·기본키 사용 불가')
        if any(not isinstance(attestation.get(name), str) or not attestation[name].strip()
               for name in ('source_id', 'evidence_state', 'source_confirmation')):
            raise ValueError('출처·근거 상태·검증 참조 누락')
        fields.append(field)

    if read_only is None:
        from app.core.db import read_only

    # information_schema의 컬럼명과 정확히 일치하는 경우만 SQL 식별자로 사용.
    metadata = read_only(
        'SELECT COLUMN_NAME FROM information_schema.COLUMNS '
        'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s', (table,)
    )
    existing = {entry['COLUMN_NAME'] for entry in metadata}
    if key not in existing or any(field not in existing for field in fields):
        raise ValueError('실제 DB의 테이블·컬럼명과 일치하지 않음')

    requested = ', '.join('`' + field + '`' for field in (key, *fields))
    rows = read_only(
        f'SELECT {requested} FROM `{table}` WHERE `{key}` = %s LIMIT 2',
        (facility_id.strip(),),
    )
    source_rows = read_only('SELECT source_id FROM source_list')
    converter = importlib.import_module('app.services.ai10.ai10_assessment_record_input')
    return converter.build_case_from_assessment(
        case_reference=case_reference, issue_description=issue_description,
        table=table, facility_id=facility_id, rows=rows,
        attestations=attestations, source_rows=source_rows,
        ck_reference=ck_reference,
    )
