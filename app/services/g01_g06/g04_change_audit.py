"""G-04 결정·설정 변경 감사기록: 운영 저장 전 검증 및 변경계획 생성.

기능정의서 v0.5.3 G-04: 누가 언제 결정·가중치·담당 부서 표를
변경했는지 보존; 설정 변경은 제안자·승인자·사유를 함께 기록.
실제 저장소, 인증, 승인 권한은 미연결. 변경계획 함수는 원본을 수정하지 않는다.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from copy import deepcopy
from typing import Any, Mapping

KINDS = frozenset({'후보 결정', '가중치 설정', '담당 부서 표'})
SETTINGS = frozenset({'가중치 설정', '담당 부서 표'})

class G04Error(ValueError):
    pass

@dataclass(frozen=True)
class ChangeRequest:
    kind: str
    target_ref: str
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    actor_ref: str
    reason: str
    proposer_ref: str | None = None
    approver_ref: str | None = None
    approval_confirmed: bool = False
    round_is_finalized: bool | None = None
    # 인증·상태·승인 근거는 상위 계층이 검증하여 전달해야 함


def prepare_change_event(req: ChangeRequest, *, observed_current: Mapping[str, Any]) -> dict:
    """낙관적 변경 전 값 검사 후 변경 계획+감사 기록 생성. DB 쓰기 없음.

    운영 연동 시 현재값 검증·변경·이력 기록을 단일 트랜잭션에 묶어야 함.
    이 함수 성공만으로 실제 변경/승인 완료를 의미하지 않음.
    """
    if req.kind not in KINDS:
        raise G04Error('지원하지 않는 변경 종류입니다.')
    for name, value in [('대상',req.target_ref),('변경자',req.actor_ref),('변경 사유',req.reason)]:
        if not isinstance(value,str) or not value.strip():
            raise G04Error(f'{name} 정보가 필요합니다.')
    if not isinstance(req.before, Mapping) or not isinstance(req.after, Mapping) or not isinstance(observed_current, Mapping):
        raise G04Error('변경 전후 및 현재값은 자료 항목으로 입력해야 합니다.')
    if not req.before or not req.after:
        raise G04Error('변경 전후 자료가 필요합니다.')
    if dict(req.before) != dict(observed_current):
        raise G04Error('변경 전 값이 현재 저장된 값과 다릅니다. 최신 자료를 다시 확인해야 합니다.')
    if dict(req.before) == dict(req.after):
        raise G04Error('변경된 값이 없습니다.')
    if req.kind == '후보 결정':
        if req.round_is_finalized is not False:
            raise G04Error('미확정 회차인지 확인되지 않았거나 확정돼 변경할 수 없습니다.')
        # G-03의 최초 기록과 구분; 역할·관할 검사 재사용은 실제 통합 시 필수.
    if req.kind in SETTINGS:
        if (not isinstance(req.proposer_ref,str) or not req.proposer_ref.strip()
            or not isinstance(req.approver_ref,str) or not req.approver_ref.strip()
            or req.approval_confirmed is not True):
            raise G04Error('설정 변경에는 제안자·승인자·확인된 승인 정보가 필요합니다.')
    event = {
        'kind':req.kind,'target_ref':req.target_ref.strip(),
        'before':deepcopy(dict(req.before)),'after':deepcopy(dict(req.after)),
        'actor_ref':req.actor_ref.strip(),'reason':req.reason.strip(),
        'proposer_ref':req.proposer_ref.strip() if req.proposer_ref else None,
        'approver_ref':req.approver_ref.strip() if req.approver_ref else None,
        'approval_confirmed':req.approval_confirmed if req.kind in SETTINGS else None,
        'occurred_at':datetime.now(timezone.utc).isoformat(),
        'record_status':'저장 전 변경 계획',
    }
    return {'proposed_value':deepcopy(dict(req.after)), 'audit_event':event,
            'write_performed':False, 'requires_atomic_persistence':True}
