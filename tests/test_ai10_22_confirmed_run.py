"""샘플 22건 상위 확정판정 연계 + 잠정후보 보호 검증."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.ai10_22_confirmed_run import run_22_confirmed_handoff


def main():
    records = json.loads((ROOT/'data'/'RADAR_AI10_민원샘플_정리_v2.json').read_text(encoding='utf-8-sig'))['records']
    passed = 0
    def check(name, condition):
        nonlocal passed
        assert condition, name
        passed += 1
        print('PASS | ' + name)

    with tempfile.TemporaryDirectory() as d:
        store = Path(d)/'review.json'
        approved = {'rule_id':'CK-03','edited_template':'검증 문장', 'review_status':'approved', 'approved':True, 'approved_at':'2026-10-20T00:00:00+00:00', 'revision':1}
        unapproved = {**approved, 'rule_id':'CK-04', 'review_status':'pending', 'approved':False}
        store.write_text(json.dumps({'items':{'CK-03':approved,'CK-04':unapproved}}, ensure_ascii=False), encoding='utf-8')
        before = store.read_bytes()
        blank = run_22_confirmed_handoff(records, store=store)
        check('22건 전체 실행', blank['counts']['total'] == 22)
        check('판정 미전달 22건 연결 차단', blank['counts']['linked'] == 0)
        check('잠정 CK 자동 확정 금지', all(x['confirmed_rule_id'] is None for x in blank['records']))
        check('기존 잠정 후보 3건 보존', sum(bool(x['ck_provisional']) for x in blank['records']) == 3)
        sample1, sample2, sample3, sample4 = [x['sample_id'] for x in records[:4]]
        results = run_22_confirmed_handoff(records, {
            sample1: {'rule_id':'CK-03','judgment_confirmed':True,'evidence_ref':'TEST-EVIDENCE-01'},
            sample2: {'rule_id':'CK-04','judgment_confirmed':True,'evidence_ref':'TEST-EVIDENCE-02'},
            sample3: {'rule_id':'CK-99','judgment_confirmed':True,'evidence_ref':'TEST-EVIDENCE-03'},
            sample4: {'rule_id':'CK-03','judgment_confirmed':False,'evidence_ref':'TEST-EVIDENCE-04'},
        }, store=store)
        by_id = {r['sample_id']:r for r in results['records']}
        check('외부 판정 4건 접수', results['counts']['confirmed_inputs'] == 4)
        check('확정 CK 승인 문장 1건 연결', results['counts']['linked'] == 1 and by_id[sample1]['proposal']['action_proposal_sentence'] == '검증 문장')
        check('미승인 CK 연결 차단', by_id[sample2]['status'] == '승인된 문장 없음')
        check('기준표 외 CK 연결 차단', by_id[sample3]['status'] == 'CK 식별자 확인 불가')
        check('미확정 판정 연결 차단', by_id[sample4]['status'] == '판정 미확정')
        check('확정 CK가 원본 잠정 후보와 달라도 임의 분류 없이 입력만 사용', by_id[sample1]['confirmed_rule_id'] == 'CK-03')
        check('입력 원문 미포함', all('complaint_claim_summary' not in r and 'sanitized_title' not in r for r in results['records']))
        check('Gemini 미호출 표기', all(r['gemini_invoked'] is False for r in results['records']))
        check('기존 승인 저장소 불변', store.read_bytes() == before)
        try:
            run_22_confirmed_handoff(records, {'NOT-IN-SAMPLES':{}}, store=store)
        except ValueError:
            check('미등록 샘플ID 입력 거절', True)
        else:
            raise AssertionError('미등록 샘플ID가 허용됨')
        check('전체 수 보존', results['counts']['linked'] + results['counts']['not_linked'] == 22)
    print(f'결과: {passed}/{passed} 통과 | 실제 Gemini/DB 호출 없음')

if __name__ == '__main__':
    main()
