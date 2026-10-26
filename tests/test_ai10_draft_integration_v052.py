"""기존 ai10_draft import API 및 최신 문장 규칙 오프라인 회귀검증."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.ai10_draft import load_rule, generate_draft, make_prompt, validate_draft, DraftOutput

def check(label, fn):
    fn(); print("PASS | "+label)

def test_ck14():
    for n in range(1,15):
        r=load_rule(f"CK-{n:02d}")
        assert r['rule_id']==f"CK-{n:02d}"

def test_prompt():
    p=make_prompt(load_rule('CK-03'))
    assert '정확히 두 문장' in p
    assert '원문(없으면 null): null' in p

def test_contract():
    import inspect
    assert list(inspect.signature(generate_draft).parameters)[0]=='rule_id'
    assert list(inspect.signature(load_rule).parameters)==['rule_id']
    o=DraftOutput(rule_id='CK-03',draft_template='자료로 점자블록의 실제 상태를 확인할 수 없습니다. 현장에서 점자블록을 확인해 주세요.',review_note='검토 필요')
    assert validate_draft(o,'CK-03')==o

def test_source_block():
    bad=DraftOutput(rule_id='CK-03',draft_template='성남시정보공개 회신에 따르면 자료가 없습니다. 현장 확인을 요청합니다.',review_note='검토 필요')
    try: validate_draft(bad,'CK-03')
    except ValueError: return
    assert False, '원문 없는 정보공개 회신 단정 차단 실패'

def test_one_sentence_block():
    bad=DraftOutput(rule_id='CK-03',draft_template='현장에서 확인해 주세요.',review_note='검토 필요')
    try: validate_draft(bad,'CK-03')
    except ValueError: return
    assert False, '한 문장 차단 실패'

if __name__=='__main__':
    for label,fn in [('최신 CK 14건',test_ck14),('두 문장 프롬프트와 출처 주의',test_prompt),('기존 함수 인터페이스',test_contract),('미검증 회신 출처 차단',test_source_block),('한 문장 차단',test_one_sentence_block)]:check(label,fn)
    print('결과: 5/5 통과 | Gemini API 호출 없음 / DB 변경 없음')
