import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.ai10_22_assessment_link import check_22_assessment_links, load_csv_tables

def main():
    records = json.loads((ROOT/'data'/'RADAR_AI10_민원샘플_정리_v2.json').read_text(encoding='utf-8-sig'))['records']
    row = {'횡단보도관리번호':'XW-01','안내_점자블록_원본':'N'}
    tables={'07_assess_crosswalk':[row]}
    total=0
    def check(title, ok):
        nonlocal total
        assert ok, title
        total+=1
        print('PASS | '+title)
    blank=check_22_assessment_links(records, {}, tables)
    check('22건 입력 보존',blank['counts']['total']==22)
    check('시설 연결표 없으면 22건 미연결',blank['counts']['unlinked']==22)
    check('잠정 CK는 확정으로 변환되지 않음',all(r['confirmed_rule_id'] is None for r in blank['records']))
    sample=records[0]['sample_id']
    links={sample:{'table':'07_assess_crosswalk','facility_id':'XW-01','evidence_ref':'TEST-ID-MAPPING'}}
    output=check_22_assessment_links(records,links,tables)
    first=output['records'][0]
    check('명시 시설ID로 한 행 연결',first['facility_id']=='XW-01')
    check('CSV 판정값 CK 후보 대조',any(x['rule_id']=='CK-03' for x in first['ck_candidates']))
    check('후보는 확정하지 않음',first['confirmed_rule_id'] is None and not first['judgment_confirmed'])
    check('근거 참조 기록',first['evidence_ref']=='TEST-ID-MAPPING')
    check('원본 민원 내용 출력 제외','sanitized_title' not in str(output))
    check('확인 근거 없는 연결 차단',check_22_assessment_links(records,{sample:{'table':'07_assess_crosswalk','facility_id':'XW-01'}},tables)['records'][0]['status']=='연결 근거 또는 시설 식별자 부족')
    check('없는 시설 식별자 거절',check_22_assessment_links(records,{sample:{'table':'07_assess_crosswalk','facility_id':'UNKNOWN','evidence_ref':'E'}},tables)['records'][0]['status']=='시설 레코드 없음')
    check('시설 ID 중복 차단',check_22_assessment_links(records,links,{'07_assess_crosswalk':[row,row]})['records'][0]['status']=='시설 식별자 중복')
    check('판정 값 없으면 CK 후보 없음',check_22_assessment_links(records,links,{'07_assess_crosswalk':[{'횡단보도관리번호':'XW-01'}]})['records'][0]['ck_candidates']==[])
    try: check_22_assessment_links(records,{'UNKNOWN':{}},tables)
    except ValueError: check('존재하지 않는 샘플 거절',True)
    else: raise AssertionError('unrecognized sample accepted')
    check('Gemini 호출 없음',all(r['gemini_invoked'] is False for r in output['records']))
    check('샘플 원본 불변',records[0]['ck_candidate']=='CK-14')
    print(f'결과: {total}/{total} 통과 | Gemini/DB 미호출')
if __name__=='__main__':main()
