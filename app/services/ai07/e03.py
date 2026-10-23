"""E-03 보수적 문장 다듬기 검사. 가상 E-02 계약만 지원한다.

숫자 집합만 비교하면 점수와 순위를 뒤바꾼 문장을 놓친다.
따라서 현재는 허용한 표현 변경 외의 모든 변경을 거부한다.
자유로운 LLM 의역 검증이나 실제 공통 LLM 연결이 완성된 것은 아니다.
DB, 네트워크, LLM 호출을 하지 않는다.
"""
from .e02 import explain_card

# 각각 같은 뜻으로 인정하는 표현. 사실을 담은 값/출처/결측은 변경 불가.
REWRITES = (
    ('의 입력값은 ', '의 제공된 값은 '),
    ('제공된 점수 기여 ', '입력된 점수 기여 '),
)
JUDGMENT_STEMS = ('위험하', '위험한', '위험합', '안전하', '안전한', '안전합',
                  '시급', '우선 정비', '문제없', '문제 없')


def suggest_local(text):
    """허용 표현만 고치는 로컬 시험용. LLM이 아니다."""
    for before, after in REWRITES:
        text = text.replace(before, after)
    return text


def _canonical(text):
    for before, after in REWRITES:
        text = text.replace(after, before)
    return text


def refine_card(card, proposed_text=None):
    """항상 원본 카드에서 기본문을 재생성한다. 외부 결과의 검증표시는 신뢰하지 않는다."""
    base = explain_card(card)
    if base['status'] != 'ok':
        return {**base, 'refinement_status': 'blocked', 'accepted': False,
                'validation_method': 'conservative_phrase_allowlist_v1'}
    original = base['explanation']
    # 실제 AI가 반환한 문장은 나중에 공통 서버 담당자가 proposed_text로 전달한다.
    proposal = suggest_local(original) if proposed_text is None else proposed_text
    errors = []
    if not isinstance(proposal, str) or not proposal.strip() or len(proposal) > 30000:
        errors.append('invalid_proposal')
    elif any(stem in proposal for stem in JUDGMENT_STEMS):
        errors.append('judgment_language')
    elif _canonical(proposal) != _canonical(original):
        errors.append('unsupported_change')
    accepted = not errors
    return {**base, 'explanation': proposal if accepted else original,
            'original_explanation': original,
            'refinement_status': 'accepted' if accepted else 'fallback',
            'accepted': accepted, 'validation_errors': errors,
            'validation_method': 'conservative_phrase_allowlist_v1',
            'generation_method': 'local_phrase_rewrite' if proposed_text is None else 'supplied_text_validation',
            'llm_called': False, 'external_api_called': False, 'db_written': False}
