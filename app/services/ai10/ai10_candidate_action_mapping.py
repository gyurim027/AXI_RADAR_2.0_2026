"""AI-10 H-06 결과 -> SQL v1.10 82 priority_candidate_action 사전 검증.

DB 접속·쓰기 없음. run_id/gid/CK와 후보 선정 여부는 호출 측에서 제공하고
실제 78/81번 참조 존재 여부는 DB 연결 후 별도 검증해야 합니다.

설치: app/services/ai10_candidate_action_mapping.py
"""
from typing import Any


class CandidateActionMappingError(ValueError):
    """82번 저장 전에 해결해야 하는 입력 문제."""


def preview_candidate_action_row(
    proposal: dict[str, Any] | None,
    *,
    run_id: int,
    gid: str,
    selected_yn: str,
    item_id: str,
) -> dict[str, Any]:
    """82번 실제 컬럼 6개에 대응하는 읽기 전용 저장 미리보기를 반환.

    created_at은 SQL DEFAULT CURRENT_TIMESTAMP에 맡겨 반환하지 않음.
    selected_yn은 78번에 실제 기록된 값이어야 하며, 여기서는 전달값만 점검.
    반환된 action_text가 대상별 치환을 마친 문장인지 호출 측에서 최종 확인 필요.
    """
    if type(run_id) is not int or run_id < 1:
        raise CandidateActionMappingError('run_id는 기존 77/78번 실행 번호에 해당하는 양의 정수여야 합니다.')
    if not isinstance(gid, str) or not gid.strip() or len(gid) > 32:
        raise CandidateActionMappingError('gid는 기존 격자 번호(빈 값 불가, 32자 이하)여야 합니다.')
    if selected_yn != 'Y':
        raise CandidateActionMappingError('82번은 78번에서 선정된 후보(selected_yn=Y)에만 사용합니다.')
    if not isinstance(item_id, str) or not item_id.startswith('CK-') or not item_id[3:].isdigit() or len(item_id) > 10:
        raise CandidateActionMappingError('item_id는 CK 형식의 기존 81번 항목ID여야 합니다.')
    if proposal is None or not isinstance(proposal, dict):
        raise CandidateActionMappingError('승인된 조치 제안 결과가 없습니다.')
    if proposal.get('rule_id') != item_id:
        raise CandidateActionMappingError('조치 제안 CK 번호와 82번 item_id가 다릅니다.')
    if proposal.get('ready_for_full_display') is not True:
        raise CandidateActionMappingError('전체 표시 준비가 되지 않은 조치 제안은 저장 후보로 넘기지 않습니다.')
    if proposal.get('missing_information') != []:
        raise CandidateActionMappingError('담당 부서 또는 근거 조문 누락 정보가 남아 있습니다.')

    names = ('action_proposal_sentence', 'receiving_department', 'confirmed_legal_basis')
    values = []
    for name in names:
        value = proposal.get(name)
        if not isinstance(value, str) or not value.strip():
            raise CandidateActionMappingError(f'82번 저장 전 {name} 값 확인이 필요합니다.')
        values.append(value.strip())

    return {
        'run_id': run_id,
        'gid': gid.strip(),
        'item_id': item_id,
        'action_text': values[0],
        'dept_text': values[1],
        'basis_text': values[2],
    }
