"""CK-03/10/14 생성 문장 보호 회귀검사. Gemini/DB 호출하지 않음."""
from app.services.ai10_draft import DraftOutput, validate_draft


def check(ck, draft, note, allowed, source=None):
    result = DraftOutput(rule_id=ck, draft_template=draft, review_note=note)
    try:
        validate_draft(result, ck, confirmed_source_text=source)
        actual = True
    except ValueError:
        actual = False
    assert actual == allowed, (ck, draft, note, actual, allowed)

cases = [
    ('CK-03','현재 자료만으로는 점자블록 상태를 확인할 수 없습니다. 현장 확인 필요성을 검토해 주세요.','확정 근거 원문이 null이므로 확인이 필요합니다.',False,None),
    ('CK-03','현재 자료만으로는 점자블록 상태를 확인할 수 없습니다. 현장 확인 필요성을 검토해 주세요.','확정 근거 원문이 제공되지 않아 확인이 필요합니다.',True,None),
    ('CK-14','신고 내역은 확인되나 반복 여부는 알 수 없습니다. 현장 확인 필요성을 검토해 주세요.','원문 대조 필요',False,None),
    ('CK-14','신고 내역은 확인되나 반복 여부는 알 수 없습니다. 현장 확인 필요성을 검토해 주세요.','원문 대조 필요',True,'담당자가 확인한 원문'),
    ('CK-14','신고 내역이 확인되는지 알 수 없습니다. 현장 확인 필요성을 검토해 주세요.','원문 대조 필요',True,None),
    ('CK-14','신고 내역이 확인되지 않았습니다. 현장 확인 필요성을 검토해 주세요.','원문 대조 필요',True,None),
    ('CK-14','신고가 반복되는지는 알 수 없습니다. 현장 확인 필요성을 검토해 주세요.','원문 대조 필요',True,None),
    ('CK-10','보도 폭 2.0m 미만 여부는 확인되지 않았습니다. 현장 실측 필요성을 검토해 주세요.','원문 대조 필요',True,None),
    ('CK-10','실제 보도 폭은 1.5m입니다. 현장 실측 필요성을 검토해 주세요.','원문 대조 필요',False,None),
]
for case in cases:
    check(*case)
print(f'AI-10 근거/품질 회귀검사 {len(cases)}/{len(cases)} 통과 | Gemini/DB 미호출')
