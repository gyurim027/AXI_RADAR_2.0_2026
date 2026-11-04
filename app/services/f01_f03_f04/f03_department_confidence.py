"""F-03 담당 부서 근거 등급 표시 (개발용, 읽기 전용).

F-01 match_department의 반환 결과를 받아 담당 부서 표의 A/B/C 근거 등급을
표시한다. 표시 결과는 승인·법률 판단이나 실제 담당 부서 확정이 아니다.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class F03ConfidenceError(ValueError):
    """호출 계약이 잘못된 경우."""


def describe_department_confidence(f01_result: Mapping[str, Any]) -> dict[str, Any]:
    """F-01 결과를 변경하지 않고 근거 등급과 확인 필요 표시를 추가한다.

    단일 일치 후보만 등급을 표시하며 A=근거 명확, B/C=해석 및 확인 필요.
    규칙 미일치·중복·근거 등급 누락·이상 등급은 안전하게 미확정으로 처리한다.
    """
    if not isinstance(f01_result, Mapping):
        raise F03ConfidenceError('F-01 결과는 매핑이어야 합니다.')
    result = deepcopy(dict(f01_result))
    status = result.get('status')
    if status not in ('1차 부서 후보', '담당 미정', '확인 필요'):
        raise F03ConfidenceError('F-01 결과 상태가 올바르지 않습니다.')

    matches = result.get('matching_rules')
    if not isinstance(matches, list):
        raise F03ConfidenceError('F-01의 규칙 일치 목록이 올바르지 않습니다.')

    base = {
        'basis_grade': None,
        'confidence_label': '근거 없음',
        'needs_human_review': True,
        'confidence_reason': '담당 부서 규칙이 확정되지 않음',
    }
    if status != '1차 부서 후보':
        base['confidence_label'] = '확인 필요' if status == '확인 필요' else '근거 없음'
        base['confidence_reason'] = str(result.get('reason') or '담당 부서 후보 없음')
    elif len(matches) != 1 or not isinstance(matches[0], dict):
        base['confidence_reason'] = '단일 일치 규칙을 확인할 수 없음'
    elif not isinstance(result.get('receiving_dept'), str) or not result['receiving_dept'].strip():
        base['confidence_reason'] = '담당 부서 후보 값 없음'
    else:
        rule = matches[0]
        grade = rule.get('basis_grade')
        grade = grade.strip().upper() if isinstance(grade, str) else None
        if grade == 'A':
            base.update(basis_grade='A', confidence_label='확인됨',
                        needs_human_review=False,
                        confidence_reason='담당 부서 표에 원문 근거가 명확한 A등급')
        elif grade in ('B', 'C'):
            base.update(basis_grade=grade, confidence_label='확인 필요',
                        needs_human_review=True,
                        confidence_reason=f'{grade}등급: 근거 해석 또는 담당자 확인 필요')
        else:
            base['confidence_reason'] = '유효한 근거 등급(A/B/C)이 없으므로 확인 필요'
            base['confidence_label'] = '확인 필요'

    # 원본과 중첩 규칙 목록은 독립 복사: 입력 자료를 변경하지 않는다.
    result.update(base)
    result['department_finalized'] = False
    return result
