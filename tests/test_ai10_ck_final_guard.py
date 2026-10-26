"""외부 서비스 및 DB 호출 없는 CK 식별자/CK-10 검증."""
from app.services.ai10_draft import DraftOutput, validate_draft
from app.services.ai10_h06_ck_correspondence import compare_judgment_to_ck, validate_external_ck

cases = [
    ('보도 폭은 1.5m입니다. 현장 조치를 검토해 주세요.', False),
    ('보도 폭은 기준 미달입니다. 현장 조치를 검토해 주세요.', False),
    ('보도 폭이 2.0m 이하입니다. 현장 조치를 검토해 주세요.', False),
    ('보도 폭은 2.0m 미만으로 확인됐습니다. 현장 조치를 검토해 주세요.', False),
    ('보도 폭 2.0m 미만 여부는 확인되지 않았습니다. 현장 실측을 검토해 주세요.', True),
    ('보도 폭 실측 자료가 없습니다. 현장 실측을 검토해 주세요.', True),
    ('보도 폭이 기준 미달인지 확인되지 않았습니다. 현장 실측을 검토해 주세요.', True),
]
for sent, should_pass in cases:
    try:
        validate_draft(DraftOutput(rule_id='CK-10', draft_template=sent, review_note='검토'), 'CK-10')
        passed=True
    except ValueError:
        passed=False
    assert passed == should_pass, (sent, passed, should_pass)

assert validate_external_ck('CK-03')['status']=='식별자 확인'
assert validate_external_ck('CK-99')['status']=='기준표에 없음'
assert validate_external_ck(None)['status']=='입력 부족'
assert compare_judgment_to_ck('점자블록 없음 (11곳)')['status']=='대응 후보 1건'
assert compare_judgment_to_ck(None)['status']=='입력 부족'
assert compare_judgment_to_ck('보도에 차가 주차됨')['status']=='대응 없음'
print('CK 독립 검증 13/13 통과 | 실제 DB/Gemini 미호출')
