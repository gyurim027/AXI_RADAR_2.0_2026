"""고정 SELECT만 실행하는 DB 조회기 (AI-07, 진이 원본 로직 유지).

공통 서버로 옮기며 바뀐 것: 연결은 app/core/db.py(.env의 RADAR_DB_*)를 쓴다. 화면 입력·DB 이름 고정은 없앰.
읽기 전용 거래·고정 SELECT·바인딩 인자·롤백·닫기는 그대로다."""

from decimal import Decimal

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


def stored_explanation(row, *, details=None):
    if row['score'] is None or row['rank_no'] is None:
        return None
    # 점수·순위는 계산하지 않는다. 저장값이 이상하면 해석하지 않고 보류한다.
    score, rank = Decimal(str(row['score'])), row['rank_no']
    if not score.is_finite() or not 0 <= score <= 100 or type(rank) is not int or rank < 1:
        raise ValueError('invalid_stored_values')
    text = (
        f"실행 {row['run_id']}의 격자 {row['gid']}의 저장 점수는 {row['score']}점이며, "
        f"저장 순위는 {rank}위입니다. "
    )
    if row['rule_version'] is None:
        text += '규칙 버전은 미제공입니다. '
    else:
        text += f"규칙 버전은 {row['rule_version']}입니다. "
    if details and details.get('stored'):
        return text + ('상세근거 5종은 함께 제공된 저장 자료를 확인해 주세요. '
            '민원 건수만으로 점수 기여를 추정하지 않았습니다. '
            '미평가 사유와 신뢰도는 위험 점수와 구분해야 합니다. '
            '공식 승인 여부와 산식 타당성은 이 저장값 설명으로 확인할 수 없습니다.')
    return text + (
        '항목별 점수 기여·지표별 출처·기준일과 민원의 점수 반영 여부는 이번 조회에 제공되지 않았습니다. '
        '따라서 순위의 원인이나 민원 0건 여부를 추정하지 않았습니다. '
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
