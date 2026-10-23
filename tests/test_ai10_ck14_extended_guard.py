"""CK-14 출처 미확정 단정 및 정상적인 불확실성 표현 경계 검증. API/DB 호출 없음."""
from app.services.ai10_draft import DraftOutput, validate_draft

CASES = [
 ('신고 이력은 존재하나', False),
 ('신고 이력은 존재하지만', False),
 ('신고 이력은 존재합니다', False),
 ('신고 내역은 확인되나', False),
 ('신고 내역은 확보됐습니다', False),
 ('신고 이력이 존재하는지 확인되지 않았습니다', True),
 ('신고 이력은 아직 확인되지 않았습니다', True),
 ('신고 이력은 존재하지 않습니다', True),
 ('신고 이력이 확인되었다고 볼 수 없습니다', True),
 ('신고 내역은 존재한다고 보기 어렵습니다', True),
 ('신고 내역이 확인되는지 알 수 없습니다', True),
 ('신고가 반복되는지는 알 수 없습니다', True),
 ('해당 신고 이력은 존재하나 반복 여부는 모릅니다', False),
]
for part, expected in CASES:
    draft = f'{part}. 현장 확인 후 조치 필요성을 검토해 주세요.'
    try:
        validate_draft(DraftOutput(rule_id='CK-14',draft_template=draft,review_note='원문 확인 필요'), 'CK-14')
        actual = True
    except ValueError:
        actual = False
    assert actual == expected, (part, actual, expected)
# 근거가 사람에 의해 전달된 경우 문장 검사 자체는 허용
validate_draft(DraftOutput(rule_id='CK-14',draft_template='신고 이력은 존재합니다. 현장 확인을 검토해 주세요.',review_note='원문 확인 필요'), 'CK-14', confirmed_source_text='운영자 확인 원문')
print(f'CK-14 사실 단정 경계검사 {len(CASES)+1}/{len(CASES)+1} 통과 | API/DB 미호출')
