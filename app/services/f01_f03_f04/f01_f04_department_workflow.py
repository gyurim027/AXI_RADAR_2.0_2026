"""F-01 → F-03 → F-04: 독립 서비스를 재사용한 표시 전용 통합.

실제 규칙/업무분장 수집, 사용자 인증, DB 쓰기, 담당부서 확정은 범위 밖.
원본의 임의 속성(특히 개인 담당자 정보)을 표시 응답에 노출하지 않는다.
"""
from __future__ import annotations

from app.services.f01_department_rules import match_department
from app.services.f03_department_confidence import describe_department_confidence
from app.services.f04_department_contact import attach_department_contact


def describe_department(*, problem_kind, road_kind, protected_zone, rules, directory) -> dict:
    """규칙→근거 등급→공식 대표 연락처를 하나의 업무 표시 결과로 반환."""
    matched = match_department(problem_kind=problem_kind, road_kind=road_kind,
                               protected_zone=protected_zone, rules=rules)
    confidence = describe_department_confidence(matched)
    contact = attach_department_contact(confidence, directory=directory)
    # 서비스 내부에서 유지하는 원본 matching_rules에는 선택적 외부 필드가 있을 수 있음.
    # 프런트엔드용 반환값에는 허용된 업무 표시 속성만 담는다.
    allowed = (
        'status', 'reason', 'receiving_dept', 'rule_id', 'source_ref',
        'basis_grade', 'confidence_label', 'confidence_reason',
        'needs_human_review', 'department_finalized',
        'jurisdiction_id', 'dept_team', 'dept_phone', 'contact_source_ref',
        'contact_status', 'contact_reason',
    )
    result = {key: contact.get(key) for key in allowed}
    result['source'] = 'F-01 → F-03 → F-04 / supplied rules and directory'
    result['storage'] = '읽기 전용 / DB 미연결'
    return result
