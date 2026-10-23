"""개발 전용: CK 선택적 사례 초안을 H-07 임시 JSON 검토 저장소에 인계.

운영 문장 틀 ID 발급·MySQL 저장·운영 승인·G-06 대상 연결을 수행하지 않는다.
원본 사례 입력과 민원 개인정보는 저장하지 않는다.
"""
from pathlib import Path
from app.services.ai10_operator_review import atomic_save, load_store, now


class CaseReviewBridgeError(ValueError):
    pass


def stage_case_draft(result: dict, store: Path) -> str:
    """명시적으로 호출될 때만 개발용 미승인 초안을 1건 등록한다.

    반환되는 DEVCASE 식별자는 임시 검토 키이며 action_template.item_id가 아니다.
    """
    if not isinstance(result, dict) or result.get('db_written') is not False:
        raise CaseReviewBridgeError('DB 미저장 결과만 개발용으로 인계할 수 있습니다.')
    if result.get('model_call_allowed') is not True or result.get('review_status') != '미승인':
        raise CaseReviewBridgeError('생성된 미승인 초안만 인계할 수 있습니다.')
    draft = result.get('draft')
    if not isinstance(draft, dict):
        raise CaseReviewBridgeError('생성 결과가 없습니다.')
    reference = result.get('case_reference')
    if not isinstance(reference, str) or not reference.strip() or reference != draft.get('case_reference'):
        raise CaseReviewBridgeError('사례 식별값이 일치하지 않습니다.')
    if len(reference) > 80 or any(ord(c) < 32 for c in reference):
        raise CaseReviewBridgeError('개발용 사례 식별값 형식이 올바르지 않습니다.')
    sentence = draft.get('draft_template')
    note = draft.get('review_note')
    if not isinstance(sentence, str) or not sentence.strip() or not isinstance(note, str) or not note.strip():
        raise CaseReviewBridgeError('초안 문장 또는 운영자 확인 메모가 비어 있습니다.')
    rid = 'DEVCASE:' + reference
    store = Path(store)
    if store.exists():
        data = load_store(store)
        if not isinstance(data.get('items'), dict):
            raise CaseReviewBridgeError('검토 저장소 구조가 올바르지 않습니다.')
    else:
        data = {'purpose': '개발 전용: 운영 DB 및 문장 틀 ID 미연결', 'created_at': now(), 'items': {}}
    if rid in data['items']:
        raise CaseReviewBridgeError('이미 인계된 사례입니다. 덮어쓰지 않습니다.')
    data['items'][rid] = {
        'rule_id': rid, 'source_draft_template': sentence.strip(),
        'edited_template': sentence.strip(), 'review_note': note.strip(),
        'findings': [], 'review_status': 'pending', 'approved': False,
        'reviewer': None, 'approved_at': None, 'revision': 0, 'events': [],
        'development_only': True,
        'db_item_id': None,
    }
    atomic_save(store, data)
    return rid
