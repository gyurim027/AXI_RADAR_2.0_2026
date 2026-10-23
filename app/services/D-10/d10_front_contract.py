"""D-10 프론트 관리자 요청에 대한 *서버 내부* 연결 계약.

가상 서버의 rx1 ID를 실DB ID로 추정·변환하지 않는다.
실DB의 ID 발급·저장/산정 완료 판정/인증을 대신하지 않는다.
"""
from dataclasses import dataclass
from typing import Mapping

from app.services.d10_rounds import RoundStore, RoundError


class D10ContractError(ValueError):
    pass


FRONT_KIND_TO_DOMAIN = {'annual': '연간', 'ref': '반기 참고', '반기 참고': '반기 참고', '연간': '연간'}


def normalize_create_request(payload: Mapping) -> dict:
    """frontend admin.createRun({kind,name}) -> 내부 D-10 도메인 입력."""
    if not isinstance(payload, Mapping):
        raise D10ContractError('회차 생성 요청은 객체여야 합니다.')
    kind = payload.get('kind')
    if not isinstance(kind, str) or kind not in FRONT_KIND_TO_DOMAIN:
        raise D10ContractError('정해지지 않은 회차 종류입니다.')
    name = payload.get('name')
    if not isinstance(name, str) or not name.strip():
        raise D10ContractError('회차 이름은 필수입니다.')
    return {'name': name.strip(), 'kind': FRONT_KIND_TO_DOMAIN[kind]}


def create_development_round(store: RoundStore, payload: Mapping) -> dict:
    """독립 개발 테스트 전용. 운영 createRun 응답으로 사용 금지."""
    if not isinstance(store, RoundStore):
        raise D10ContractError('개발용 D-10 저장소가 필요합니다.')
    params = normalize_create_request(payload)
    if any(r['name'] == params['name'] for r in store.list_all()):
        return {'ok': False, 'code': 'duplicate'}
    result = store.create(**params)
    return {'ok': True, 'temporaryId': result['temporary_id'],
            'storage': 'development_memory_only', 'operationalRunId': None}


@dataclass(frozen=True)
class TrustedRoundStatus:
    """서버가 인증 및 산정 실행 결과를 직접 확인한 후 만드는 값."""
    run_id: int
    kind: str                 # 연간 / 반기 참고
    status: str               # 산정 중 / 검토 중 / 참고 / 확정
    calculation_completed: bool
    authorized_operator: bool


def plan_open_run(payload: Mapping, context: TrustedRoundStatus,
                  *, missing_sources=None, unevaluated_areas=None) -> dict:
    """frontend openRun({runId}) 전처리. 운영 DB 변경은 수행하지 않음."""
    if not isinstance(payload, Mapping) or not isinstance(context, TrustedRoundStatus):
        raise D10ContractError('요청과 검증된 서버 문맥이 필요합니다.')
    if type(context.run_id) is not int or context.run_id <= 0:
        raise D10ContractError('실DB에서 발급한 양의 정수 run_id가 필요합니다.')
    if payload.get('runId') != context.run_id:
        raise D10ContractError('회차 ID가 서버 조회값과 다릅니다. 가상 ID 대응을 추측하지 않습니다.')
    if not context.authorized_operator:
        raise D10ContractError('운영자 권한을 확인할 수 없습니다.')
    if context.kind not in ('연간', '반기 참고'):
        raise D10ContractError('회차 종류가 확정되지 않았습니다.')
    if context.status != '산정 중':
        raise D10ContractError('산정 중인 회차만 열 수 있습니다.')
    if type(context.calculation_completed) is not bool:
        raise D10ContractError('신뢰된 산정 완료 정보가 필요합니다.')
    def clean_list(values):
        if values is None:
            return []
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise D10ContractError('안내 항목은 문자열 목록이어야 합니다.')
        return list(dict.fromkeys(v.strip() for v in values if v.strip()))
    missing = clean_list(missing_sources)
    unrated = clean_list(unevaluated_areas)
    return {
        'run_id': context.run_id,
        'can_open': context.calculation_completed,
        'next_status': '검토 중' if context.kind == '연간' else '참고',
        'missing_sources': missing,
        'unevaluated_areas': unrated,
        'reason': None if context.calculation_completed else '산정이 아직 완료되지 않았습니다.',
        'operation': 'contract_only_no_write',
    }
