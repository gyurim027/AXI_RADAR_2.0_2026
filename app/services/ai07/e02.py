"""E-02 기본 설명문. 표준 라이브러리만 사용하며 I/O·DB·LLM 호출 없음.

지금 형식은 진규님 실제 근거 카드 명세가 아닌 가상 시험용 제안 계약이다.
실제 팀 입력은 별도 어댑터에서 이 형식으로 대응한 뒤 검증해야 한다.
"""
from copy import deepcopy
from decimal import Decimal
import re

SCHEMA = 'ai07.e02.synthetic.v0.1'
JUDGMENTS = ('위험하다', '안전하다', '시급하다', '우선 정비 필요')


class CardError(ValueError):
    pass


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise CardError('invalid_fields')


def _text(value, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise CardError('invalid_text')
    if any(ord(c) < 32 for c in value) or any(word in value for word in JUDGMENTS):
        raise CardError('unsupported_text')


def _year(value, nullable=False):
    if value is None and nullable:
        return
    if type(value) is not int or not 1000 <= value <= 9999:
        raise CardError('invalid_year')


def _number(value, nonnegative=False):
    # 가상 계약은 소수 문자열을 사용해 65.0000 등의 표기를 보존한다.
    if value is None:
        return
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', value):
        raise CardError('invalid_number')
    parsed = Decimal(value)
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise CardError('invalid_number')


def validate_card(card):
    _keys(card, ['schema_version', 'data_kind', 'run_id', 'gid', 'place',
                 'calculation_year', 'score', 'rank', 'total', 'rank_scope',
                 'formula_version', 'calculation_status', 'evidence'])
    if card['schema_version'] != SCHEMA or card['data_kind'] != 'synthetic':
        raise CardError('synthetic_contract_required')
    for field in ['run_id', 'gid', 'place']:
        _text(card[field])
    for field in ['rank_scope', 'formula_version']:
        _text(card[field], nullable=True)
    _year(card['calculation_year'])
    _number(card['score'], nonnegative=True)
    for field in ['rank', 'total']:
        if card[field] is not None and (type(card[field]) is not int or card[field] < 1):
            raise CardError('invalid_rank_or_total')
    if card['rank'] is not None and card['rank_scope'] is None:
        raise CardError('rank_scope_required')
    if card['rank'] is not None and card['total'] is not None and card['rank'] > card['total']:
        raise CardError('rank_exceeds_total')
    if card['calculation_status'] not in ('test_not_approved', 'approval_unknown', 'approved'):
        raise CardError('invalid_calculation_status')
    if not isinstance(card['evidence'], list) or len(card['evidence']) > 50:
        raise CardError('invalid_evidence')
    ids = set()
    for item in card['evidence']:
        _keys(item, ['evidence_id', 'run_id', 'gid', 'label', 'value', 'unit',
                     'basis_year', 'source', 'status', 'reason', 'contribution_points'])
        if item['run_id'] != card['run_id'] or item['gid'] != card['gid']:
            raise CardError('mixed_run_or_grid')
        for field in ['evidence_id', 'label']:
            _text(item[field])
        if item['evidence_id'] in ids:
            raise CardError('duplicate_evidence_id')
        ids.add(item['evidence_id'])
        for field in ['unit', 'source', 'reason']:
            _text(item[field], nullable=True)
        _year(item['basis_year'], nullable=True)
        _number(item['value'])
        _number(item['contribution_points'])
        if item['status'] == 'observed':
            if item['value'] is None or item['unit'] is None or item['reason'] is not None:
                raise CardError('observed_value_required')
        elif item['status'] in ('missing', 'unassessed'):
            if item['value'] is not None or item['contribution_points'] is not None or item['reason'] is None:
                raise CardError('missing_value_conflict')
        else:
            raise CardError('invalid_evidence_status')


def explain_card(card):
    """설명 생성 실패 시 임의 기본값 없이 blocked/explanation=None 반환.

    실제 입력값은 수정하지 않으며, 0과 결측·미평가를 구분한다.
    """
    try:
        validate_card(card)
    except CardError as exc:
        return {'schema_version': SCHEMA, 'status': 'blocked', 'error_codes': [str(exc)],
                'explanation': None, 'external_api_called': False, 'db_written': False}

    facts = deepcopy(card)
    year = card['calculation_year']
    score = '점수 모름' if card['score'] is None else f"점수 {card['score']}점"
    if card['rank'] is None:
        rank = '순위 모름'
    else:
        if card['total'] is None:
            rank = f"{card['rank_scope']}의 입력 순위 {card['rank']}위(전체 대상 수 미제공)"
        else:
            rank = f"{card['rank_scope']} 대상 {card['total']}개 격자 중 입력 순위 {card['rank']}위"
    version = card['formula_version'] or '미제공'
    status = {'test_not_approved': '승인 전 시험 결과',
              'approval_unknown': '결과 승인 여부 미확인',
              'approved': '입력에 승인 상태로 표시된 결과'}[card['calculation_status']]
    # 첫 문장의 연도는 산정연도이며 아래 근거별 자료 기준연도와 구분한다.
    summary = (f"{year}년 산정 기준 {card['place']} 격자 {card['gid']}의 입력값은 {score}, {rank}입니다"
               f"(실행 {card['run_id']}, 산식 버전 {version}, {status})")
    chunks, sources = [], []
    for item in card['evidence']:
        basis = '자료 기준연도 미확인' if item['basis_year'] is None else f"{item['basis_year']}년 자료"
        source = f"출처: {item['source']}" if item['source'] is not None else '출처 미확인'
        if item['status'] == 'observed':
            value = f"{item['value']}{item['unit']}"
        else:
            kind = '미평가' if item['status'] == 'unassessed' else '자료 없음'
            value = f"모름({kind}, 사유: {item['reason']})"
        part = f"{basis}, {item['label']}: {value}"
        if item['contribution_points'] is not None:
            part += f", 제공된 점수 기여 {item['contribution_points']}점"
        chunks.append(f"{part}({source})")
        sources.append({'evidence_id': item['evidence_id'], 'basis_year': item['basis_year'],
                        'source': item['source']})
    detail = '; '.join(chunks) if chunks else '항목별 근거는 모름(근거 카드에 미제공)'
    # E-02는 문장 틀로 생성. 출처/결측을 빼고 LLM처럼 짧게 요약하지 않는다.
    explanation = summary + '. ' + detail + '.'
    limitations = []
    if any(i['basis_year'] is None for i in card['evidence']):
        limitations.append('일부 근거의 자료 기준연도가 미확인입니다.')
    if any(i['source'] is None for i in card['evidence']):
        limitations.append('일부 근거의 출처가 미확인입니다.')
    if any(i['status'] != 'observed' for i in card['evidence']):
        limitations.append('자료 없음과 미평가를 0으로 채우지 않았습니다.')
    if any(i['contribution_points'] is None for i in card['evidence']) or not card['evidence']:
        limitations.append('미제공 기여점수나 순위의 원인은 추정하지 않았습니다.')
    return {'schema_version': SCHEMA, 'status': 'ok', 'data_kind': 'synthetic',
            'run_id': card['run_id'], 'gid': card['gid'], 'facts': facts,
            'generation_method': 'local_template', 'explanation': explanation,
            'sentences': [summary + '.', detail + '.'], 'source_refs': sources,
            'limitations': limitations, 'error_codes': [],
            'external_api_called': False, 'db_written': False}
