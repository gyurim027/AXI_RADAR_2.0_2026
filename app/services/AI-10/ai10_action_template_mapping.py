"""AI-10 개발용 JSON -> SQL v2 81 action_template 저장값 사전 검증.

DB 쓰기·접속 없음. SQL에 없는 상태나 이력 필드를 생성하지 않음.
이 모듈은 현행 스키마와의 기술적 대응만 검사하며 운영 승인 정책을 확정하지 않음.
"""
from datetime import datetime, timezone

class MappingError(ValueError):
    """저장 전 검토가 필요한 입력."""


def preview_action_template_update(item: dict, reviewer_user_id: int | None = None) -> dict:
    """81번 테이블에 대응하는 검토 관련 값만 반환 (INSERT/UPDATE 실행 없음).

    reviewer_user_id는 기존 app_user.user_id여야 하며, 이 함수는 DB 존재 여부를 확인할 수 없다.
    rejected나 모순된 상태는 정책 없이 '초안'으로 바꾸지 않는다.
    """
    rid = item.get('rule_id')
    if not isinstance(rid, str) or not rid.startswith('CK-') or not rid[3:].isdigit():
        raise MappingError('올바른 CK 식별자가 필요합니다.')
    status, approved = item.get('review_status'), item.get('approved')
    if status == 'pending' and approved is False:
        db_status = '초안'
    elif status == 'approved' and approved is True:
        db_status = '검토 완료'
    elif status == 'rejected' and approved is False:
        raise MappingError('반려 상태는 81번의 별도 상태로 정의되지 않았습니다. 운영 규칙 확인이 필요합니다.')
    else:
        raise MappingError('검토 상태와 승인 여부가 불일치하거나 알 수 없는 상태입니다.')

    sentence = item.get('edited_template')
    if sentence is not None and not isinstance(sentence, str):
        raise MappingError('조치 제안 문장은 문자열 또는 NULL이어야 합니다.')
    sentence = sentence.strip() if isinstance(sentence, str) else None
    sentence = sentence or None
    # 81번 초기 데이터: 문장 없는 CK는 검토 상태도 NULL로 유지한다.
    # 문장이 존재하는 미승인 CK만 '초안'으로 표시한다.
    if db_status == '초안' and sentence is None:
        db_status = None
    if db_status == '검토 완료' and sentence is None:
        raise MappingError('검토 완료 상태에서 문장이 비어 있습니다.')

    if reviewer_user_id is not None and (type(reviewer_user_id) is not int or reviewer_user_id < 1):
        raise MappingError('검토자는 app_user.user_id에 해당하는 양의 정수여야 합니다.')
    # DB에 존재하는 실제 사용자 번호인지는 DB 조회 후 별도 확인 필요.
    if db_status == '검토 완료' and reviewer_user_id is None:
        raise MappingError('검토 완료 문장에는 실제 운영자 user_id 확인이 필요합니다.')

    approved_at = item.get('approved_at')
    if db_status != '검토 완료':
        if approved_at is not None:
            raise MappingError('미승인 상태인데 승인 시각이 존재합니다.')
        reviewed_at = None
    else:
        if not isinstance(approved_at, str) or not approved_at.strip():
            raise MappingError('검토 완료 상태에는 승인 시각이 필요합니다.')
        try:
            dt = datetime.fromisoformat(approved_at.replace('Z', '+00:00'))
        except ValueError as exc:
            raise MappingError('승인 시각이 ISO 8601 형식이 아닙니다.') from exc
        if dt.tzinfo is None:
            raise MappingError('승인 시각의 시간대가 명시되어야 합니다.')
        reviewed_at = dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=' ', timespec='seconds')
        # UTC 기준 문자열이며 실제 MySQL 세션/운영 시간대 정책은 별도 확인 필요.

    return {
        'item_id': rid,
        'action_sentence': sentence,
        'sentence_review_status': db_status,
        'reviewer': reviewer_user_id,
        'reviewed_at': reviewed_at,
    }
