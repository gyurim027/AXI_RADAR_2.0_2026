"""고정 SELECT만 실행하는 DB 조회기 (AI-07, 진이 원본 로직 유지).

공통 서버로 옮기며 바뀐 것: 연결은 app/core/db.py(.env의 RADAR_DB_*)를 쓴다. 화면 입력·DB 이름 고정은 없앰.
읽기 전용 거래·고정 SELECT·바인딩 인자·롤백·닫기는 그대로다."""

from decimal import Decimal, InvalidOperation

SCHEMA = 'ai07.db-readonly.v1'
RUN_SQL = '''SELECT run_id, build_id, rule_version, created_at
FROM priority_run ORDER BY run_id DESC LIMIT 21'''
CANDIDATE_SQL = '''SELECT run_id, gid, selected_yn, score, rank_no
FROM priority_candidate WHERE run_id = %s
ORDER BY rank_no IS NULL, rank_no, gid LIMIT 101'''
DETAIL_SQL = '''SELECT p.run_id, p.gid, p.selected_yn, p.score, p.rank_no,
r.build_id, r.rule_version, r.created_at
FROM priority_candidate AS p JOIN priority_run AS r ON p.run_id = r.run_id
WHERE p.run_id = %s AND p.gid = %s LIMIT 1'''


def envelope(**values):
    return {'schema_version': SCHEMA, 'data_origin': 'server_db',
            'read_only': True, 'external_api_called': False, **values}


def serialize(row):
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, Decimal):
            result[key] = str(value)  # 4자리 소수와 값을 변형하지 않는다.
        elif key == 'run_id':
            result[key] = str(value)  # JavaScript의 큰 정수 손실 방지
        elif key == 'created_at' and value is not None:
            result[key] = value.isoformat(sep=' ')
    return result


DETAIL_LABELS = (
    ('domain_scores', '분야별 점수'),
    ('indicator_contributions', '지표별 기여도'),
    ('unevaluated_reasons', '미평가 사유'),
    ('confidence_grade', '신뢰도'),
    ('score_excluding_accidents', '사고 제외 점수'),
    ('exclusion_reasons', '제외 사유'),
    ('complaint_contribution', '민원 기여점'),
    ('policy_version', '근거 정책 판본'),
)


def _stored_number(value, *, score=False):
    if isinstance(value, bool):
        raise ValueError('invalid_stored_values')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('invalid_stored_values') from None
    if not number.is_finite() or (score and not 0 <= number <= 100):
        raise ValueError('invalid_stored_values')
    return number


def stored_explanation(row):
    if row['score'] is None or row['rank_no'] is None:
        return None
    # 점수·순위는 계산하지 않는다. 저장값이 이상하면 해석하지 않고 보류한다.
    _stored_number(row['score'], score=True)
    rank = row['rank_no']
    if type(rank) is not int or rank < 1:
        raise ValueError('invalid_stored_values')
    text = (
        f"실행 {row['run_id']}의 격자 {row['gid']}의 저장 점수는 {row['score']}점이며, "
        f"저장 순위는 {rank}위입니다. "
    )
    rule_version = row.get('rule_version')
    text += ('규칙 버전은 미제공입니다. ' if rule_version is None
             else f'규칙 버전은 {rule_version}입니다. ')

    details = row.get('details')
    if not isinstance(details, dict) or details.get('stored') is not True:
        text += '저장 상세근거는 이번 조회에 제공되지 않았습니다. '
    else:
        present = [(key, label) for key, label in DETAIL_LABELS
                   if details.get(key) is not None]
        missing = [label for key, label in DETAIL_LABELS
                   if details.get(key) is None]
        if present:
            text += '저장 상세근거로 ' + '·'.join(label for _, label in present) + ' 항목이 제공됩니다. '
        else:
            text += '저장 상세근거의 값은 이번 조회에서 모두 미제공입니다. '
        if missing:
            text += '미제공 또는 미평가 항목은 ' + '·'.join(missing) + '입니다. '
        contribution = details.get('complaint_contribution')
        if contribution is not None:
            _stored_number(contribution)
            text += f'저장된 민원 기여점은 {contribution}점입니다. '
        if details.get('score_excluding_accidents') is not None:
            value = details['score_excluding_accidents']
            _stored_number(value, score=True)
            text += f'저장된 사고 제외 점수는 {value}점입니다. '
        policy_version = details.get('policy_version')
        if policy_version is not None:
            text += f'상세근거의 정책 판본은 {policy_version}입니다. '
            if rule_version is not None and str(policy_version) != str(rule_version):
                text += '회차 규칙 버전과 상세근거 정책 판본의 표기가 달라 동일 판본인지는 별도 확인이 필요합니다. '

    return text + (
        '지표별 원천 자료·기준일은 이 설명에서 확인하지 않았습니다. '
        '저장값만으로 순위의 원인이나 민원 건수를 추정하지 않습니다. '
        '결과 승인 여부와 산식 확정 여부도 이번 조회로 확인할 수 없습니다. '
        '이 설명은 DB 저장값을 문장으로 표시한 것이며 원자료나 점수 산식을 재검산한 결과가 아닙니다.'
    )

class ReadOnlyRepository:
    def __init__(self, connect):
        self.connect = connect

    def _read(self, sql, args=()):
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                # 지원되지 않으면 실패한다. 쓰기 가능한 일반 거래로 우회하지 않는다.
                cursor.execute('START TRANSACTION READ ONLY')
                cursor.execute(sql, args)
                return [serialize(row) for row in cursor.fetchall()]
        finally:
            try:
                connection.rollback()
            finally:
                connection.close()

    def runs(self):
        rows = self._read(RUN_SQL)
        return envelope(status='ok' if rows else 'no_results', runs=rows[:20], truncated=len(rows) > 20)

    def candidates(self, run_id):
        rows = self._read(CANDIDATE_SQL, (run_id,))
        return envelope(run_id=run_id, status='ok' if rows else 'no_results',
                        candidates=rows[:100], truncated=len(rows) > 100)

    def explanation(self, run_id, gid):
        rows = self._read(DETAIL_SQL, (run_id, gid))
        if not rows:
            return envelope(run_id=run_id, gid=gid, status='not_found', explanation=None)
        row = rows[0]
        text = stored_explanation(row)
        return envelope(run_id=run_id, gid=gid, status='ok' if text else 'missing_values',
                        candidate=row, explanation=text, generation_method='local_template')


def core_repository():
    """공통 DB 연결(app/core/db.py)로 저장소를 만든다. 연결은 조회 한 번마다 새로 열고 닫는다."""
    from app.core import db
    return ReadOnlyRepository(db.raw_connection)
