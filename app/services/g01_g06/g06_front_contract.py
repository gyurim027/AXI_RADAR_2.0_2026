"""G-06 전용: 기존 프론트 getConfirmSummary/confirmGu와 도메인 흐름 연결.

개발용 ReviewWorkflow에 한정. 인증·실DB·HTTP·회차상태 검증을 구현하지 않는다.
운영에서는 서버가 신뢰한 문맥을 제공하기 전 호출하지 않는다.
"""
from dataclasses import dataclass
from typing import Mapping

from app.services.g03_g06_workflow import ReviewWorkflow
from app.services.g06_round_finalize import DISTRICTS


class G06ContractError(ValueError):
    pass


@dataclass(frozen=True)
class TrustedFinalizeContext:
    run_id: int
    actor_ref: str
    actor_role: str  # '구 도로관리팀' 또는 '시 도로과'
    actor_gu: str | None
    run_is_reviewing: bool
    read_only: bool = False
    # 실제 UI의 확정 액션이 있었는지 인증/요청 라우터가 검사해 전달해야 함.
    confirmation_action_verified: bool = False


def _check(workflow: ReviewWorkflow, payload: Mapping, context: TrustedFinalizeContext):
    if not isinstance(workflow, ReviewWorkflow) or not isinstance(payload, Mapping) or not isinstance(context, TrustedFinalizeContext):
        raise G06ContractError('기존 업무 흐름, 요청 및 서버 확인 문맥이 필요합니다.')
    if type(context.run_id) is not int or context.run_id <= 0 or payload.get('runId') != context.run_id:
        raise G06ContractError('실제 정수 회차 ID가 서버 조회값과 일치해야 합니다.')
    if not isinstance(context.actor_ref, str) or not context.actor_ref.strip():
        raise G06ContractError('서버에서 확인된 행위자 식별값이 필요합니다.')


def preview_front_confirm(*, workflow: ReviewWorkflow, payload: Mapping, context: TrustedFinalizeContext) -> dict:
    """조회 전용: 구 사용자에겐 자기 구 건수, 시 사용자에겐 3개 구 확정 현황."""
    _check(workflow, payload, context)
    if context.actor_role == '시 도로과':
        statuses = workflow.finalizations.list_run(context.run_id)
        return {'role': 'city', 'guStatuses': [
            {'gu': gu, 'done': bool(statuses[gu]), 'date': None} for gu in ('수정구', '중원구', '분당구')
        ], 'note': '확정일자는 개발 저장소에 없어 제공하지 않음'}
    if context.actor_role != '구 도로관리팀' or context.actor_gu not in DISTRICTS:
        raise G06ContractError('허용되지 않은 조회 권한입니다.')
    record = workflow.finalizations.get(context.run_id, context.actor_gu)
    if record is not None:
        return {'role': 'district', 'gu': context.actor_gu,
                'counts': {'target': record['selected_count'], 'exclude': record['excluded_count'],
                           'hold': record['held_count'], 'none': record['undecided_count']},
                'mine': {'gu': context.actor_gu, 'done': True, 'date': None},
                'requiresReconfirmation': bool(record['requires_reconfirmation'])}
    preview = workflow.preview_finalize(context.run_id, context.actor_gu)
    return {'role': 'district', 'gu': context.actor_gu,
            'counts': {'target': preview['selected_count'], 'exclude': preview['excluded_count'],
                       'hold': preview['held_count'], 'none': preview['undecided_count']},
            'mine': {'gu': context.actor_gu, 'done': False, 'date': None},
            'requiresReconfirmation': preview['requires_reconfirmation'],
            'undecidedGids': preview['undecided_gids']}


def apply_front_confirm(*, workflow: ReviewWorkflow, payload: Mapping, context: TrustedFinalizeContext) -> dict:
    """프론트 confirmGu({runId}) -> G-06. 미결정 재확인은 현 프론트 계약으론 차단."""
    _check(workflow, payload, context)
    if context.actor_role != '구 도로관리팀' or context.actor_gu not in DISTRICTS or context.read_only:
        raise G06ContractError('확정은 수정 가능한 자기 구 도로관리팀만 할 수 있습니다.')
    if context.run_is_reviewing is not True:
        raise G06ContractError('검토 중인 연간 회차에서만 확정할 수 있습니다.')
    if context.confirmation_action_verified is not True:
        raise G06ContractError('서버에서 확인된 명시적 구별 확정 액션이 필요합니다.')
    preview = workflow.preview_finalize(context.run_id, context.actor_gu)
    if preview['requires_reconfirmation']:
        raise G06ContractError(
            f"미결정 후보 {preview['undecided_count']}건: 프론트 confirmGu 요청에 별도 재확인값이 없어 확정을 보류합니다. 프론트 담당자와 협의가 필요합니다."
        )
    result = workflow.finalize(
        run_id=context.run_id, gu=context.actor_gu, actor_ref=context.actor_ref,
        actor_role=context.actor_role, actor_gu=context.actor_gu,
        explicitly_confirmed=True, reconfirm_undecided=False,
    )
    return {'ok': True, 'gu': result['gu'], 'done': True,
            'roundFinalized': result['round_finalized'],
            'storage': result['storage'],
            'calculationConditionsRecord': result['calculation_conditions_record']}
