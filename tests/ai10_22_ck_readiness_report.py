"""22건의 CK 연계 준비 상태 점검. 민원 주장을 판정하지 않고 기존 자료를 보고한다.
실행: uv run python tests/ai10_22_ck_readiness_report.py
"""
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data'/'RADAR_AI10_민원샘플_정리_v2.json'
RULES=ROOT/'data'/'ai10_ck_rules_v0.4.1.json'
OUTPUT=ROOT/'reports'/'ai10_22건_CK적용_준비상태.json'

def report(records, rules):
    valid={r['rule_id'] for r in rules}
    rows=[]
    for rec in records:
        ck=rec.get('ck_candidate')
        scope=rec.get('ai10_test_scope','검토 전')
        if ck and ck in valid:
            status='잠정 CK 후보 · 판정 근거 미연결'
            next_step='상위 판정 기능의 확인된 CK 적용 근거 및 운영자 승인 필요'
        elif ck:
            status='CK 식별자 기준표 불일치'
            next_step='기존 CK 식별자와 입력 출처 확인 필요'
        elif scope=='비대상':
            status='샘플 검토상 비대상 · CK 미연결'
            next_step='현재 자료만으로 CK 연계하지 않음; 대상 범위 재검토 시 공식 근거 필요'
        elif scope=='조건부':
            status='조건부 · 판정 근거 미제공'
            next_step='기존 판정 기능의 대상·위치·시설 상태 확인 결과 필요'
        else:
            status='검토 전 · 판정 근거 미제공'
            next_step='담당 기능의 대상 여부 및 확인된 판정 결과 필요'
        rows.append({'sample_id':rec['sample_id'],'source_row_number':rec['source_row_number'],
            'sanitized_title':rec['sanitized_title'],'sample_scope':scope,
            'ck_provisional':ck,'ck_applied':False,'reason':status,
            'unverified':rec.get('not_verified'),'required_next_input':next_step,
            'gemini_invoked':False,'operator_approved':False})
    return {'report_type':'AI-10 샘플 22건 CK 연계 준비 상태',
        'note':'샘플의 기존 분류·잠정 CK만 사용; 실제 판정·CK 확정·Gemini 호출·DB 저장 없음',
        'counts':{'all':len(rows),'provisional_ck':sum(bool(r['ck_provisional']) for r in rows),
                  'ck_missing':sum(not r['ck_provisional'] for r in rows),
                  'scope':dict(Counter(r['sample_scope'] for r in rows)),
                  'ck_applied':0},'records':rows}

def main():
    sample=json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    rules=json.loads(RULES.read_text(encoding='utf-8-sig'))['rules']
    result=report(sample['records'],rules)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in result['records']:
        print(f"{row['sample_id']} | {row['reason']} | {row['ck_provisional'] or 'CK 없음'}")
    print(f"총 {result['counts']['all']}건 | 잠정 CK {result['counts']['provisional_ck']}건 | 확정 CK 0건 | Gemini/DB 미호출")
    print(f'저장: {OUTPUT}')
if __name__=='__main__':main()
