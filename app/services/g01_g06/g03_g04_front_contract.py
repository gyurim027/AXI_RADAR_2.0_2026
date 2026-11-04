"""G-03/G-04 프론트 saveDecision 입력의 개발용 연결 계층.

프론트/공통 서버를 수정하지 않는다. 인증/관할/회차 상태/사유 목록은
신뢰된 서버 계층이 확인하여 TrustedDecisionContext로 전달해야 한다.
DB 저장, HTTP 라우터, 사용자 인증, 가상 ID 변환은 이 파일의 책임이 아니다.
"""
from dataclasses import dataclass
from typing import Mapping

from app.services.g03_candidate_decision import DecisionRequest
from app.services.g03_g06_workflow import ReviewWorkflow


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class TrustedDecisionContext:
    run_id: int
    gid: str
    actor_ref: str
    actor_role: str
    actor_gu: str
    weight_version: str
    run_is_reviewing: bool  # DB/운영 서버가 확인한 값. 프론트 요청을 신뢰하지 말 것.
    read_only: bool = False


def apply_front_decision(*, workflow: ReviewWorkflow, payload: Mapping,
                         context: TrustedDecisionContext, decision_map: Mapping[str, str],
                         reason_map: Mapping[str, str]):
    """프론트 saveDecision 데이터 -> 개발용 G-03 최초 결정 또는 G-04 변경.

    결정값 및 사유값 대응표는 프론트 constants / 공식 사유 목록 확인 후 외부 주입.
    최초 기록과 변경은 기존 결정 존재 여부로 구분하고, 변경 사유는 별도 필수.
    반환값은 내부 계약 결과이며 프론트의 {ok:true} 운영 응답을 보장하지 않는다.
    """
    if not isinstance(workflow, ReviewWorkflow) or not isinstance(context, TrustedDecisionContext):
        raise ContractError('검증된 업무 흐름과 서버 인증 문맥이 필요합니다.')
    if not isinstance(payload, Mapping) or not isinstance(decision_map, Mapping) or not isinstance(reason_map, Mapping):
        raise ContractError('요청 데이터와 확정된 상태·사유 대응표가 필요합니다.')
    if type(context.run_id) is not int or context.run_id <= 0:
        raise ContractError('서버에서 발급한 양의 정수 run_id가 필요합니다. rx1 같은 가상 ID는 사용할 수 없습니다.')
    if payload.get('runId') != context.run_id or payload.get('gid') != context.gid:
        raise ContractError('프론트 요청 후보와 서버에서 확인한 회차·후보가 다릅니다.')
    if not context.run_is_reviewing or context.read_only:
        raise ContractError('검토 중인 회차의 수정 가능한 계정만 결정을 저장할 수 있습니다.')
    raw_decision = payload.get('decision')
    if not isinstance(raw_decision, str) or raw_decision not in decision_map:
        raise ContractError('확정된 프론트 결정 상태 대응표에 없는 값입니다.')
    decision = decision_map[raw_decision]
    if decision not in {'우선 점검 대상', '제외', '보류'}:
        raise ContractError('결정 상태 대응표가 잘못되었습니다.')
    raw_reason = payload.get('reasonKey')
    if raw_reason == '기타':
        raise ContractError('기타 사유의 reasonText 저장 계약을 먼저 협의해야 합니다.')
    if raw_reason is not None and (not isinstance(raw_reason, str) or raw_reason not in reason_map):
        raise ContractError('확정된 사유 대응표에 없는 값입니다.')
    reason_code = reason_map[raw_reason] if raw_reason is not None else None
    if reason_code is not None and reason_code not in workflow.reason_codes:
        raise ContractError('백엔드 허용 사유 목록에 없는 값입니다.')
    memo = payload.get('memo') or ''
    if not isinstance(memo, str):
        raise ContractError('메모는 문자열이어야 합니다.')
    if len(memo) > 200:
        raise ContractError('프론트 규칙을 초과하는 메모입니다(최대 200자).')
    existing = workflow.decisions.get(context.run_id, context.gid)
    if existing is None:
        result = workflow.add_decision(DecisionRequest(
            run_id=context.run_id, gid=context.gid, decision=decision,
            reason_code=reason_code, memo=memo,
            weight_version=context.weight_version, actor_ref=context.actor_ref,
            actor_role=context.actor_role, actor_gu=context.actor_gu))
        return {'operation': 'G-03 최초 결정', 'record': result,
                'storage': 'development_memory_only'}
    change_reason = payload.get('changeReason')
    if not isinstance(change_reason, str) or not change_reason.strip():
        raise ContractError('G-04 기존 결정 변경에는 별도의 변경 사유(changeReason)가 필요합니다. 프론트 협의 대상입니다.')
    result = workflow.change_decision(
        run_id=context.run_id, gid=context.gid,
        actor_ref=context.actor_ref, actor_role=context.actor_role,
        actor_gu=context.actor_gu, new_decision=decision,
        new_reason_code=reason_code, new_memo=memo,
        reason=change_reason.strip())
    return {'operation': 'G-04 기존 결정 변경', **result}
