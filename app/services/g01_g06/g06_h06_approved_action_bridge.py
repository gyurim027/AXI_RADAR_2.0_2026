"""G-06 개발용 회차 확정 결과 -> H-06 승인 문장 조회 연결.

읽기 전용 조회만 수행한다. 후보별 조치 유형·판정 종류는 상위 기능이
실제 근거를 확인한 뒤 제공해야 하며, DB 저장/문장 치환/Gemini 호출은 없다.
"""
from __future__ import annotations

from app.services.ai10_h06_template_lookup import (
    find_approved_templates, resolve_approved_template
)


class HandoffError(ValueError):
    pass


def lookup_for_finalized_candidate(*, workflow, cursor, run_id: int, gid: str,
                                   judgement_kind: str | None = None,
                                   action_kind: str | None = None,
                                   check_item: str | None = None) -> dict:
    """전체 회차 확정 + 해당 후보의 인간 결정이 '우선 점검 대상'일 때만 조회.

    판단/조치 항목은 후보 식별자만으로 계산하지 않는다. 하나라도 없으면
    H-06 조회를 건너뛰고 자료 연결 필요를 명시한다.
    """
    if type(run_id) is not int or run_id <= 0 or not isinstance(gid, str) or not gid.strip():
        raise HandoffError('올바른 회차 실행 번호와 격자 번호가 필요합니다.')
    candidate = workflow.candidates.find(run_id, gid)
    if candidate is None:
        raise HandoffError('해당 회차에 존재하지 않는 후보입니다.')
    if not workflow.finalizations.round_finalized(run_id):
        raise HandoffError('3개 구의 확정이 완료되지 않은 회차입니다.')
    gu = candidate['gu']
    if workflow.finalizations.get(run_id, gu) is None:
        raise HandoffError('후보가 속한 구의 확정 기록이 없습니다.')
    decision = workflow.decisions.get(run_id, gid)
    if decision is None or decision.get('decision') != '우선 점검 대상':
        return {'run_id': run_id, 'gid': gid, 'eligible': False,
                'status': 'not_priority_inspection_target', 'item_id': None,
                'action_sentence': None, 'db_write_performed': False}
    if (not isinstance(judgement_kind, str) or not judgement_kind.strip()
        or not isinstance(action_kind, str) or not action_kind.strip()):
        return {'run_id': run_id, 'gid': gid, 'eligible': True,
                'status': 'assessment_or_action_kind_not_provided', 'item_id': None,
                'action_sentence': None, 'db_write_performed': False}
    matches = find_approved_templates(cursor, judgement_kind, action_kind, check_item)
    status, resolved = resolve_approved_template(matches)
    return {'run_id': run_id, 'gid': gid, 'eligible': True, 'status': status,
            'item_id': resolved['item_id'] if resolved else None,
            'action_sentence': resolved['action_sentence'] if resolved else None,
            'db_write_performed': False,
            'note': '승인 문장 틀 조회 결과일 뿐 후보별 조치 확정·DB 저장은 아님'}
