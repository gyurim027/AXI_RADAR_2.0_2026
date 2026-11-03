"""F-01 담당 부서 1차 규칙 적용.

기능정의서 v0.5.3 03_상세기능목록 F-01: 문제 유형·도로 종류·보호구역 안팎과
사무위임 조례·규칙에 근거한 담당 부서 표를 대조한다. 일치하지 않으면 담당 미정.
담당 부서 규칙은 외부에서 공급되며 이 모듈은 어떤 기관도 임의로 지정하지 않는다.
운영 DB 조회·수정 없음.
"""
from __future__ import annotations

from copy import deepcopy

CONTEXT_KEYS = ('problem_kind', 'road_kind', 'protected_zone')
REQUIRED_RULE = (*CONTEXT_KEYS, 'receiving_dept', 'source_ref')


class F01RuleError(ValueError):
    pass


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def match_department(*, problem_kind, road_kind, protected_zone, rules):
    """확정된 담당 부서 표를 받아 안전한 1차 결과를 구성한다.

    일치 1건: 후보를 제시(최종 담당 부서 확정 아님)
    일치 0건/입력 누락: 담당 미정
    일치 2건 이상: 선택 보류 (중복 규칙 오류를 감추지 않음)

    rules: problem_kind/road_kind/protected_zone/receiving_dept/source_ref
    필수; 선택: rule_id, basis_grade, jurisdiction_id, dept_team, dept_phone.
    """
    if not isinstance(rules, (list, tuple)):
        raise F01RuleError('담당 부서 표는 규칙 목록이어야 합니다.')
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or any(not _nonempty(rule.get(k)) for k in REQUIRED_RULE):
            raise F01RuleError(f'담당 부서 표 {i+1}번째 행에 필수 항목이 없습니다.')
    incoming = dict(zip(CONTEXT_KEYS, (problem_kind, road_kind, protected_zone)))
    if any(not _nonempty(v) for v in incoming.values()):
        return {'status': '담당 미정', 'reason': '문제 유형·도로 종류·보호구역 안팎 중 입력 누락',
                'receiving_dept': None, 'matching_rules': [], 'needs_human_review': True}
    normalized = {k: v.strip() for k,v in incoming.items()}
    matches = [deepcopy(r) for r in rules if all(r[k].strip() == normalized[k] for k in CONTEXT_KEYS)]
    if not matches:
        return {'status': '담당 미정', 'reason': '담당 부서 표에 일치하는 조합 없음',
                'receiving_dept': None, 'matching_rules': [], 'needs_human_review': True}
    if len(matches) != 1:
        return {'status': '확인 필요', 'reason': '동일 조건 규칙이 여러 건 일치하여 자동 선택 보류',
                'receiving_dept': None, 'matching_rules': matches, 'needs_human_review': True}
    rule = matches[0]
    return {'status': '1차 부서 후보', 'reason': '담당 부서 표 단일 규칙 일치 / 담당자 확정 전',
            'receiving_dept': rule['receiving_dept'].strip(),
            'matching_rules': matches, 'needs_human_review': False,
            'source_ref': rule['source_ref'], 'rule_id': rule.get('rule_id'),
            'basis_grade': rule.get('basis_grade'), 'jurisdiction_id': rule.get('jurisdiction_id')}
