"""F-01/F-03: evidence-gated, read-only department selection.

This module does NOT infer 18 legal task types from the 9 score indicators.
The input `verified_problem` must come from a trusted internal classification
with a durable evidence reference, never directly from user query parameters.
Condition_text is unstructured: do not silently evaluate it from F-02.
"""
from __future__ import annotations
from typing import Callable, Mapping, Any

DISTRICTS = frozenset({"수정구", "중원구", "분당구"})


def resolve_verified_department(
    *, gu: str | None,
    verified_problem: Mapping[str, Any] | None,
    read_reference: Callable[[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Return frontend contract. Never fabricate a department for incomplete evidence.

    read_reference is the existing 87/88 read_department_reference function.
    Conditional reference rows block automatic selection even if a road type
    string was supplied: natural-language conditions need an approved rule.
    """
    jurisdiction_id = (verified_problem or {}).get('jurisdictionId')
    evidence_status = (verified_problem or {}).get('evidenceStatus')
    evidence_ref = (verified_problem or {}).get('evidenceRef')
    road_type = (verified_problem or {}).get('roadType')
    inputs = {'gu': gu, 'jurisdictionId': jurisdiction_id, 'roadType': road_type,
              'evidenceRef': evidence_ref}

    def unresolved(reason: str, *, options: list | None = None) -> dict[str, Any]:
        return {'department': None, 'departmentStatus': '확인 필요',
                'departmentReason': reason, 'departmentInputs': inputs,
                'departmentOptions': options or []}

    if gu not in DISTRICTS:
        return unresolved('관할 구가 검증되지 않았습니다.')
    if not isinstance(jurisdiction_id, str) or not jurisdiction_id.startswith('JUR-'):
        return unresolved('확정된 18개 문제 유형과 연결된 관할 ID가 없습니다.')
    if evidence_status != '확인됨' or not isinstance(evidence_ref, str) or not evidence_ref.strip():
        return unresolved('문제 유형의 검증 상태 또는 원천 근거 식별자가 부족합니다.')
    try:
        reference = read_reference(jurisdiction_id, gu)
    except (LookupError, ValueError):
        return unresolved('관할 기준표에서 해당 문제 유형을 확인할 수 없습니다.')
    if reference.get('jurisdictionId') != jurisdiction_id or reference.get('gu') != gu:
        return unresolved('관할 기준 조회 결과의 연결 키가 일치하지 않습니다.')
    if reference.get('basisStatus') != '확인됨':
        return unresolved('관할 기준 자체가 확인된 상태가 아닙니다.')
    options = reference.get('options') or []
    # 87/88 contains unstructured conditions and competing organization levels.
    # Even when one unconditional row exists, a conditional row may override it.
    if not options:
        return unresolved('해당 구에 적용 가능한 담당 부서 기준이 없습니다.')
    if any(not isinstance(o, dict) or o.get('needsConditionCheck') or o.get('condition') for o in options):
        return unresolved('담당 부서별 추가 조건이 있어 자동으로 한 부서를 확정할 수 없습니다.', options=options)
    if len(options) != 1:
        return unresolved('담당 부서 후보가 복수이므로 자동으로 한 부서를 확정할 수 없습니다.', options=options)
    chosen = options[0]
    if not chosen.get('name') or not chosen.get('referenceId'):
        return unresolved('담당 부서 기준 행에 이름 또는 근거 식별자가 없습니다.', options=options)
    return {
        'department': {'name': chosen['name'], 'confidence': None,
                       'reason': '확인된 문제 유형과 관할 구에 대해 조건 없는 단일 업무분장 행이 존재합니다.',
                       'referenceId': chosen['referenceId']},
        'departmentStatus': '판정됨',
        'departmentReason': '기존 관할 기준표 87·88번의 단일 무조건 행에 따라 연결했습니다.',
        'departmentInputs': inputs,
        'departmentOptions': options,
    }
