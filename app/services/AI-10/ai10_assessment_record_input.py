"""판정 레코드 -> AI-10 CaseInput 입력 연결 (읽기 전용, 출처 확인 필수).

DB 조회/CSV 로딩은 호출자가 수행한다. 이 모듈은 source_list.used_tables로
SRC를 추정하거나 자동 LLM 호출/DB 저장을 수행하지 않는다.
"""
from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any

TABLE_KEYS = {
    'assess_crosswalk': 'crosswalk_mgmt_no',
    'assess_sidewalk': 'UFID',
    'assess_intersection': 'intersection_id',
    'assess_zone': 'zone_id',
}
CSV_TABLE_NAMES = {
    '07_assess_crosswalk': 'assess_crosswalk',
    '08_assess_sidewalk': 'assess_sidewalk',
    '09_assess_intersection': 'assess_intersection',
    '10_assess_zone': 'assess_zone',
}


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ''


def build_case_from_assessment(
    *, case_reference: str, issue_description: str,
    table: str, facility_id: str, rows: Sequence[Mapping[str, Any]],
    attestations: Sequence[Mapping[str, str]], source_rows: list[dict[str, Any]],
    ck_reference: str | None = None,
) -> dict[str, Any]:
    """특정 시설 1행과 사전 확인된 컬럼-SRC 근거만 받아 CaseInput 구축.

    attestations 항목 필수: field, source_id, source_confirmation, evidence_state.
    반환값은 CaseInput/evidence 감사 정보이며 AI 호출이나 DB 쓰기는 없다.
    """
    table = CSV_TABLE_NAMES.get(table, table)
    if table not in TABLE_KEYS:
        raise ValueError('판정 테이블 미지원')
    key = TABLE_KEYS[table]
    if not _nonempty(facility_id) or not _nonempty(case_reference) or not _nonempty(issue_description):
        raise ValueError('사례·문제 설명·시설 식별자 필요')
    if not isinstance(rows, (list, tuple)):
        raise TypeError('판정 레코드 배열 필요')
    matches = [r for r in rows if isinstance(r, Mapping) and str(r.get(key) or '').strip() == facility_id.strip()]
    if len(matches) != 1:
        raise ValueError(f'시설 ID가 정확히 한 행과 일치해야 합니다: {len(matches)}건')
    if not attestations:
        raise ValueError('검증된 근거 연결 없음: AI 입력 생성 중단')
    bridge = importlib.import_module('app.services.AI-10.ai10_assessment_evidence_bridge')
    case_module = importlib.import_module('app.services.AI-10.ai10_case_draft')
    row = matches[0]
    evidence = []
    audits = []
    fields_seen: set[str] = set()
    for a in attestations:
        field = a.get('field', '')
        if field == key or field in fields_seen or not _nonempty(row.get(field)):
            raise ValueError(f'근거 컬럼 중복·식별자·값 부재: {field}')
        fields_seen.add(field)
        result = bridge.build_assessment_evidence(
            table=table, row=row, field=field, record_key=f'{key}={facility_id.strip()}',
            source_id=a.get('source_id', ''), evidence_state=a.get('evidence_state', ''),
            source_rows=source_rows, source_confirmation=a.get('source_confirmation', ''),
        )
        # 기존 bridge의 결과만 사용한다. raw_value/좌표/도형 자동 첨부 금지.
        evidence.append(case_module.EvidenceItem(**result['evidence']))
        audits.append({'field': field, 'source_id': a['source_id'],
                       'source_confirmation': result['source_confirmation'],
                       'value_included_in_prompt': False,
                       'external_transfer_approved': False})
    case = case_module.CaseInput(
        case_reference=case_reference.strip(), issue_description=issue_description.strip(),
        evidence_items=evidence, facility_id=facility_id.strip(), ck_reference=ck_reference,
    )
    return {'case': case, 'provenance_audit': audits,
            'llm_invoked': False, 'db_written': False,
            'external_transfer_approved': False}
