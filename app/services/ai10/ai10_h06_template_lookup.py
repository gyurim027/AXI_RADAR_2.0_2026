"""H-06 승인 문장 틀 읽기 전용 조회. DB 접속·쓰기·문장 생성은 호출자 책임 범위 밖.

실제 MySQL 연결은 주입받은 DB-API 커서로만 이루어진다. 작업 중인
G-06 회차 확정이나 대상별 action_text 치환을 추론하지 않는다.
"""

class TemplateLookupError(ValueError):
    pass


# SQL에 실제로 정의된 컬럼만 사용; 포맷/식별자 문자열 보간 금지.
_LOOKUP_SQL = ("SELECT item_id, judgement_kind, check_item, action_kind, action_sentence, "
               "sentence_review_status FROM action_template "
               "WHERE judgement_kind = %s AND action_kind = %s "
               "AND sentence_review_status = '검토 완료' "
               "AND action_sentence IS NOT NULL "
               "AND TRIM(action_sentence) <> ''")
_COLUMNS = ('item_id', 'judgement_kind', 'check_item', 'action_kind',
            'action_sentence', 'sentence_review_status')


def find_approved_templates(cursor, judgement_kind: str, action_kind: str,
                            check_item: str | None = None) -> list[dict]:
    """기존 DB에서 승인 문장 후보들을 읽는다. *선택/저장하지 않는다*.

    check_item=None이면 확인 항목별로 모든 후보가 나올 수 있다.
    다중 후보는 resolve_approved_template이 보류 처리한다.
    """
    for label, value in (('판정 결과 종류', judgement_kind), ('조치 종류', action_kind)):
        if not isinstance(value, str) or not value.strip():
            raise TemplateLookupError(f'{label} 입력이 필요합니다.')
    if check_item is not None and (not isinstance(check_item, str) or not check_item.strip()):
        raise TemplateLookupError('확인 항목은 문자열 또는 None이어야 합니다.')
    query = _LOOKUP_SQL
    params = [judgement_kind.strip(), action_kind.strip()]
    if check_item is not None:
        query += ' AND check_item = %s'
        params.append(check_item.strip())
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    output = []
    for row in rows:
        if isinstance(row, dict):
            item = {key: row[key] for key in _COLUMNS}
        else:
            if len(row) != len(_COLUMNS):
                raise TemplateLookupError('DB 조회 컬럼 개수가 명세와 다릅니다.')
            item = dict(zip(_COLUMNS, row))
        # SQL 필터 외에 실제 반환값도 검증: 테스트 커서/부정확한 연결 방어
        if (item['judgement_kind'] != judgement_kind.strip() or
            item['action_kind'] != action_kind.strip() or
            item['sentence_review_status'] != '검토 완료' or
            not isinstance(item['action_sentence'], str) or
            not item['action_sentence'].strip() or
            (check_item is not None and item['check_item'] != check_item.strip())):
            raise TemplateLookupError('조회 결과가 승인 문장 조회 조건과 다릅니다.')
        output.append(item)
    return output


def resolve_approved_template(candidates: list[dict]) -> tuple[str, dict | None]:
    """명확히 한 건만 존재할 때 반환. 복수 후보 우선순위를 임의로 만들지 않는다."""
    if not candidates:
        return 'no_match', None
    if len(candidates) != 1:
        return 'multiple_matches_review_required', None
    return 'single_approved_template', candidates[0]
