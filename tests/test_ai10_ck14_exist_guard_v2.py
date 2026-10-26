"""CK-14 신규 표현 및 Gemini 1회 재시도 회귀검사: 실제 API/DB 호출 없음."""
import pytest
from pathlib import Path
_REFERENCE = Path(__file__).resolve().parents[1] / 'data' / 'ai10_reference' / 'seongnam_mobility_plan_excerpt_2026.json'
if not _REFERENCE.is_file():
    pytest.skip('AI-10 공개 참고자료 미배치: 테스트 수집 시 skip', allow_module_level=True)

from app.services.ai10_draft import DraftOutput, validate_draft, make_prompt

CASES = [
    ('신고 내역은 있으나 반복 여부는 확인할 수 없습니다.', False),
    ('신고 내역이 있습니다.', False),
    ('신고 이력은 있지만 현재 반복 여부는 알 수 없습니다.', False),
    ('신고 기록이 있으며 반복 여부는 알 수 없습니다.', False),
    ('신고 내역이 있는지 확인되지 않았습니다.', True),
    ('신고 내역이 있는지 알 수 없습니다.', True),
    ('신고 내역은 확인되지 않았습니다.', True),
    ('신고 이력은 존재하지 않습니다.', True),
    ('신고 이력의 존재 여부는 확인되지 않았습니다.', True),
]
for line, allowed in CASES:
    result = DraftOutput(rule_id='CK-14', draft_template=line + ' 담당자는 원문 확인 후 조치 필요성을 검토해야 합니다.', review_note='원문 확인 필요')
    try:
        validate_draft(result, 'CK-14')
        actual = True
    except ValueError:
        actual = False
    assert actual == allowed, (line, actual, allowed)

rule = {'rule_id': 'CK-14', 'data_limitation': '신고는 있지만 지금도 주정차가 반복되는지는 모른다'}
prompt = make_prompt(rule)
assert '유형별 가정' in prompt and '신고 내역이 있다' in prompt
assert '유형별 가정' not in make_prompt(rule, confirmed_source_text='운영자가 검증한 실제 자료')
print(f'CK-14 추가 단정 경계 및 프롬프트 {len(CASES)+2}/{len(CASES)+2} 통과 | API/DB 미호출')
