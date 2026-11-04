"""AI-07 가상 입력 시험 (원래 backend/ai07/server.py의 입력 검사·설명 부분, 진이 원본 로직 유지).

화면 목업이 보내는 가상 후보 한 건을 검사하고 문장 틀로 설명한다. DB·외부 API를 쓰지 않는다.
"""
import math
import re

from app.services.ai07.local_explainer import explain_frontend_candidate

SCHEMA = 'ai07.frontend-mock.v1'
MAX_BYTES = 64 * 1024


def require_text(value, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 1500:
        raise ValueError('invalid_text')


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'data_kind', 'facts'}:
        raise ValueError('invalid_request')
    if payload['schema_version'] != SCHEMA or payload['data_kind'] != 'frontend_mock':
        raise ValueError('invalid_profile')
    facts = payload['facts']
    keys = {'runId', 'runName', 'gid', 'score', 'rank', 'evidence'}
    if not isinstance(facts, dict) or set(facts) != keys:
        raise ValueError('invalid_facts')
    for key in ('runId', 'runName', 'gid'):
        require_text(facts[key])
    score, rank = facts['score'], facts['rank']
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError('invalid_score')
    if type(rank) is not int or not 1 <= rank <= 10000000:
        raise ValueError('invalid_rank')
    evidence = facts['evidence']
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise ValueError('invalid_evidence')
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {'item', 'value', 'basisYear', 'source'}:
            raise ValueError('invalid_evidence')
        require_text(item['item'])
        require_text(item['value'], nullable=True)
        require_text(item['source'], nullable=True)
        year = item['basisYear']
        if year is not None and (type(year) is not int or not 1900 <= year <= 9999):
            raise ValueError('invalid_year')
    return facts


def explain_request(payload):
    facts = validate_request(payload)
    result = explain_frontend_candidate(facts)
    return {**result, 'schema_version': SCHEMA, 'data_kind': 'frontend_mock', 'facts': facts}


def run_id_arg(values):
    """실행 번호 검사 (원래 db_server.run_id_arg). values = 같은 이름으로 들어온 값 목록."""
    if len(values) != 1 or not re.fullmatch(r'[0-9]{1,19}', values[0]):
        raise ValueError('invalid_run')
    if int(values[0]) > 9223372036854775807:
        raise ValueError('invalid_run')
    return values[0]
