"""민원 샘플 최신 22건: 기존 형식에 따른 CK별 Gemini 초안 출력·기록.
실행: uv run python tests/test_ai10_complaint_latest_compare_v052.py --all --generate
원문 미전송; CK 잠정후보 재판정 안 함; 운영 승인·DB 저장 안 함.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
SAMPLE=DATA/'RADAR_AI10_민원샘플_정리_v2.json'
RULES=DATA/'ai10_ck_rules_v0.4.1.json'

def read(path):
    if not path.is_file(): raise FileNotFoundError(f'필수 자료 없음: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def diagnose_link(record, rulemap):
    """22건 시험의 CK 미적용 원인을 판정과 별개로 분리한다."""
    ck = record.get('ck_candidate')
    if not ck:
        return {'stage': 'CK 입력 이전', 'reason': '샘플에 CK 잠정 후보 미입력',
                'gemini_attempted': False, 'ck_applied': False,
                'required_next_input': '공식 판정 기능의 확인된 결과 또는 검증된 CK 전달값'}
    if ck not in rulemap:
        return {'stage': 'CK 기준표 대조', 'reason': '입력된 CK가 공식 기준표에 없음',
                'gemini_attempted': False, 'ck_applied': False,
                'required_next_input': 'CK 식별자 원천 확인'}
    return {'stage': 'CK 잠정 후보 대조', 'reason': '잠정 후보가 존재하나 확정 판정·승인 아님',
            'gemini_attempted': False, 'ck_applied': False,
            'required_next_input': '확정 판정 근거 및 운영자 승인'}


def build(records,rulemap,generate=False):
    cache={}
    if generate:
        sys.path.insert(0,str(ROOT))
        from app.services.ai10_draft import generate_draft
    result=[]
    for r in records:
        ck=r.get('ck_candidate');rule=rulemap.get(ck)
        if rule and generate and ck not in cache:
            try:
                print(f'[생성] 최신 기준 {ck} Gemini 유형별 초안 생성 요청',flush=True)
                d=generate_draft(ck)
                cache[ck]={'status':'생성됨 (미승인)', 'draft_template':d.draft_template,'review_note':d.review_note}
            except Exception as e:
                cache[ck]={'status':'생성 실패','error':f'{type(e).__name__}: {e}'}
        newest=cache.get(ck) if rule else None
        diagnostic=diagnose_link(r, rulemap)
        if newest:
            diagnostic['gemini_attempted'] = True
            diagnostic['stage'] = 'Gemini 유형별 문장 생성'
            diagnostic['reason'] = ('CK 유형별 초안 생성 완료(미승인)' if newest.get('draft_template')
                                    else 'Gemini 호출 오류: CK 매핑 문제와 별개')
        result.append({
           'ck_link_diagnostic': diagnostic,
           'sample_id':r['sample_id'],'source_row_number':r['source_row_number'],
           'sanitized_title':r['sanitized_title'], 'claim_summary':r['complaint_claim_summary'],
           'verification_status':r['fact_status'], 'unverified':r['not_verified'],
           'ck_candidate':ck,'ck_link_status':r['ck_mapping_status'],
           'ck_confirmed':False,'latest_ck_rule':rule,
           'latest_generation':newest,
           'operator_approved':False,'final_candidate_proposal':None,
        })
    return result

def main():
    p=argparse.ArgumentParser()
    sel=p.add_mutually_exclusive_group();sel.add_argument('--all',action='store_true');sel.add_argument('--id')
    p.add_argument('--generate',action='store_true',help='CK 유형별 Gemini 실제 호출(비용 발생 가능)')
    p.add_argument('--output',type=Path,default=ROOT/'reports'/'ai10_민원22건_최신생성_결과.json')
    args=p.parse_args()
    samples=read(SAMPLE);rulefile=read(RULES)
    records=samples['records'] if args.all else [r for r in samples['records'] if r['sample_id']==(args.id or 'SAMPLE-01')]
    if not records:p.error('샘플 번호가 없습니다.')
    rmap={r['rule_id']:r for r in rulefile['rules']}
    rows=build(records,rmap,args.generate)
    report={'report_type':'AI-10 민원 샘플 기준 CK별 Gemini 생성 결과',
      'created_at_utc':datetime.now(timezone.utc).isoformat(),
      'latest_sources':['기획관리대장 v0.4.1','기능정의서 v0.5.2','ai10_ck_rules_v0.4.1.json'],
      'scope_warning':'CK 매핑은 샘플의 기존 잠정 후보로 실제 판정이 아님. 민원 원문은 Gemini에 전달하지 않음. 승인·DB 기록 없음.',
      'counts':{'samples':len(rows),
        'ck_input_missing':sum(x['ck_link_diagnostic']['stage']=='CK 입력 이전' for x in rows),
        'ck_input_unknown':sum(x['ck_link_diagnostic']['stage']=='CK 기준표 대조' for x in rows),
        'provisional_ck':sum(bool(x['latest_ck_rule']) for x in rows),
        'generated_ck_types':len(set(x['ck_candidate'] for x in rows if x['latest_generation'] and x['latest_generation'].get('draft_template')))},
      'results':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for x in rows:
        print('=' * 65)
        print(f"{x['sample_id']} | 원본 {x['source_row_number']} | {x['sanitized_title']}")
        print(f"[신고인의 주장] {x['claim_summary']}")
        print(f"[사실 확인] {x['verification_status']}")
        print(f"[미확인] {x['unverified']}")
        print(f"[연결] {x['ck_candidate'] or '없음'} / {x['ck_link_status']}")
        print(f"[미적용 단계] {x['ck_link_diagnostic']['stage']} | {x['ck_link_diagnostic']['reason']}")
        rule=x['latest_ck_rule']
        if rule:
            print(f"[CK 판정 기준] {rule['judgment_type']}")
            print(f"[CK 자료 한계] {rule['data_limitation']}")
            print(f"[CK 확인 사항] {rule['check_required']}")
            print(f"[CK 조치 종류] {rule['action_type']}")
            print(f"[법령 근거 후보/검증 전] {rule.get('legal_reference_candidate') or '없음'}")
        else:
            print('[CK 기준] 연결 대상 없음. 임의 생성 차단')
        latest=x['latest_generation']
        if latest:
            print(f"[Gemini] {latest['status']}")
            if latest.get('draft_template'):
                print(f"[CK 유형별 초안] {latest['draft_template']}")
                print(f"[운영자 확인 메모] {latest.get('review_note') or '없음'}")
            elif latest.get('error'):
                print(f"[호출 오류] {latest['error']}")
        else:
            print('[Gemini] CK 후보 없음' if not rule else '[Gemini] 최신 생성 전 (--generate 옵션 필요)')
        print('[최종 후보 조치 제안] 없음 / CK 확정·운영자 승인·대상 값 연결 전')
    print('=' * 65)
    print('이 시험은 실제 민원→CK 잠정 연결→CK별 Gemini 생성 흐름이다.')
    print('개별 민원 내용은 Gemini에 보내지 않으며 운영 최종 문장도 생성하지 않는다.')
    print(f"CK 입력 전 미적용: {report['counts']['ck_input_missing']}건 / 잠정 후보: {report['counts']['provisional_ck']}건")
    print(f"완료: 총 {len(rows)}건 / 최신 Gemini 생성 CK 유형 {report['counts']['generated_ck_types']}개 / 기록 {args.output}")
    print('시험 결과는 미승인·DB 미저장·CK 잠정 연결 상태입니다.')
if __name__=='__main__':main()
