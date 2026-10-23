"""RADAR AI-10 v0.5.2 통합 회귀시험: 실제 Gemini/DB 호출 없음.
기존 함수 유지, 81→H-06→82 및 CK 프롬프트/근거 조건 동시 확인.
"""
import sys, json, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.services.ai10_draft import load_rule, make_prompt, validate_draft, DraftOutput
from app.services.ai10_action_template_mapping import preview_action_template_update
from app.services.ai10_action_proposal import compose_action_proposal
from app.services.ai10_candidate_action_mapping import (
    preview_candidate_action_row, CandidateActionMappingError
)

def main():
    n=0
    def check(name,ok):
        nonlocal n
        if not ok: raise AssertionError(name)
        n+=1
        print('PASS | '+name)

    r=load_rule('CK-03')
    check('최신 CK-03 로드',r['rule_id']=='CK-03')
    check('두 문장/근거 주의 프롬프트', '정확히 두 문장' in make_prompt(r) and '근거 상태 "확인됨"' in make_prompt(r))
    check('출처 단정 차단',_invalid(DraftOutput(rule_id='CK-03',draft_template='성남시정보공개 회신에 따르면 자료가 없습니다. 확인해 주세요.',review_note='확인 필요')))

    sentence='현재 확보한 자료만으로 해당 장소의 점자블록 상태를 확인할 수 없습니다. 현장에서 점자블록 설치 여부와 연속성을 확인하고 필요한 조치를 검토해 주세요.'
    check('두 문장 초안 형식',validate_draft(DraftOutput(rule_id='CK-03',draft_template=sentence,review_note='원문 확인 필요'),'CK-03').draft_template==sentence)
    approved={'rule_id':'CK-03','edited_template':sentence,'review_status':'approved',
              'approved':True,'reviewer':'가상 운영자','approved_at':'2026-10-19T03:30:15+00:00',
              'revision':1,'events':[{'action':'approve'}],'findings':[]}
    pending={**approved,'rule_id':'CK-04','review_status':'pending','approved':False,'approved_at':None}
    with tempfile.TemporaryDirectory(prefix='ai10_regression_') as td:
        store=Path(td)/'review.json'
        store.write_text(json.dumps({'items':{'CK-03':approved,'CK-04':pending}},ensure_ascii=False),encoding='utf-8')
        before=store.read_bytes()
        row81=preview_action_template_update(approved,reviewer_user_id=3)
        check('81번 승인 문장 매핑',row81['문장_검토_상태']=='검토 완료' and row81['조치_제안_문장']==sentence)
        proposal=compose_action_proposal('CK-03',confirmed_department='시험 부서',confirmed_legal_basis='시험 조문',store=store)
        check('H-06 승인 문장 제공',proposal is not None and proposal['action_proposal_sentence']==sentence)
        check('H-06 미승인 차단',compose_action_proposal('CK-04',confirmed_department='시험 부서',confirmed_legal_basis='시험 조문',store=store) is None)
        row82=preview_candidate_action_row(proposal,run_id=7,gid='GRID-001',selected_yn='Y',item_id='CK-03')
        check('82번 문자열 gid 및 6개 컬럼',row82['gid']=='GRID-001' and len(row82)==6)
        check('82번 당시 문장 동일 보존',row82['action_text']==sentence)
        check('82번 미선정 후보 차단',_mapping_invalid(proposal,selected_yn='N'))
        check('82번 미확인 조문 차단',_mapping_invalid({**proposal,'confirmed_legal_basis':None,'missing_information':['확인된 근거 조문'],'ready_for_full_display':False}))
        check('시험 원본 불변',store.read_bytes()==before)
    print(f'결과: {n}/{n} 통과 | Gemini/API/실제 DB 호출 없음')

def _invalid(output):
    try:validate_draft(output,'CK-03')
    except ValueError:return True
    return False

def _mapping_invalid(proposal,selected_yn='Y'):
    try:preview_candidate_action_row(proposal,run_id=7,gid='GRID-001',selected_yn=selected_yn,item_id='CK-03')
    except CandidateActionMappingError:return True
    return False

if __name__=='__main__': main()
