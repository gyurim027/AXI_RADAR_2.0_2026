"""F-04 담당 팀·대표 연락처 표시 (개발용, 읽기 전용).

기능정의서 v0.5.3 F-04: F-01 1차 담당 부서에 대한 팀명 및 대표 연락처를
시청·구청 업무분장 자료로 보강한다. 개인 담당자 이름이나 개인 연락처는 사용하지 않는다.
실제 업무분장 수집/갱신(A-12), 담당 부서 최종 결정, DB 저장은 이 모듈의 범위 밖이다.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


class F04ContactError(ValueError):
    """부서 표시 계약 또는 업무분장 자료의 형식 오류."""


def _txt(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def attach_department_contact(
    f03_result: Mapping[str, Any],
    *,
    directory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """F-03 결과와 확인된 공식 업무분장 목록을 받아 후보 상세 표시 정보를 제공한다.

    directory 행 필수: receiving_dept, dept_team, dept_phone, source_ref.
    선택: jurisdiction_id. dept_phone에는 조직 대표 연락처만 공급해야 한다.
    중복 매칭 또는 불명확한 관할, 불완전한 기록에서는 연락처를 표시하지 않는다.
    제공 데이터에 개인정보가 들어와도 개인 담당자 속성을 출력으로 복사하지 않는다.
    """
    if not isinstance(f03_result, Mapping):
        raise F04ContactError('F-03 결과는 매핑이어야 합니다.')
    if not isinstance(directory, (list, tuple)):
        raise F04ContactError('업무분장 자료는 목록이어야 합니다.')
    for i, record in enumerate(directory):
        if not isinstance(record, Mapping):
            raise F04ContactError(f'업무분장 {i + 1}번째 행이 올바르지 않습니다.')
        if not all(_txt(record.get(k)) for k in ('receiving_dept', 'dept_team', 'dept_phone', 'source_ref')):
            raise F04ContactError(f'업무분장 {i + 1}번째 행에 필수값이 없습니다.')
        if 'jurisdiction_id' in record and record['jurisdiction_id'] is not None and not _txt(record['jurisdiction_id']):
            raise F04ContactError(f'업무분장 {i + 1}번째 행의 관할 값이 올바르지 않습니다.')

    result = deepcopy(dict(f03_result))
    status = result.get('status')
    if status not in ('1차 부서 후보', '담당 미정', '확인 필요'):
        raise F04ContactError('F-03의 담당 부서 상태가 올바르지 않습니다.')
    matches = result.get('matching_rules')
    if not isinstance(matches, list):
        raise F04ContactError('F-03의 일치 규칙 목록이 올바르지 않습니다.')

    display = {
        'dept_team': None,
        'dept_phone': None,
        'contact_source_ref': None,
        'contact_status': '정보 없음',
        'contact_reason': '공식 업무분장과 연결된 팀·대표 연락처 없음',
        'department_finalized': False,
    }
    if status != '1차 부서 후보' or len(matches) != 1 or not isinstance(matches[0], dict):
        display['contact_reason'] = 'F-01 담당 부서 후보가 단일하게 정해지지 않음'
    elif not _txt(result.get('receiving_dept')):
        display['contact_reason'] = '담당 부서 후보 값이 없음'
    else:
        dept = _txt(result['receiving_dept'])
        jurisdiction = _txt(matches[0].get('jurisdiction_id'))
        # 관할이 정해진 경우 다른 관할이나 관할 미표기 행을 섞지 않는다.
        candidates = [r for r in directory if _txt(r['receiving_dept']) == dept and
                      (_txt(r.get('jurisdiction_id')) == jurisdiction if jurisdiction else
                       r.get('jurisdiction_id') is None)]
        if len(candidates) == 1:
            r = candidates[0]
            display.update(
                dept_team=_txt(r['dept_team']), dept_phone=_txt(r['dept_phone']),
                contact_source_ref=_txt(r['source_ref']), contact_status='표시 가능',
                contact_reason='공식 업무분장 단일 일치 / 대표 연락처(제공 자료 기준)',
            )
        elif len(candidates) > 1:
            display['contact_status'] = '확인 필요'
            display['contact_reason'] = '업무분장 항목이 여러 건 일치해 자동 선택 보류'
    # 원본의 matching_rules를 보존하되 개인 속성은 화면 표시 전용 결과에 추가하지 않음.
    result.update(display)
    return result
