"""확정 CK 연계 독립시험: 원문/Gemini/DB 호출 없음."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.ai10_confirmed_ck_handoff import handoff_confirmed_ck


def main():
    ok = 0
    def check(label, condition):
        nonlocal ok
        assert condition, label
        ok += 1
        print('PASS | ' + label)

    sentence = '현장 상태 확인 후 필요한 조치를 검토합니다.'
    approved = {'rule_id': 'CK-03', 'edited_template': sentence,
                'review_status': 'approved', 'approved': True,
                'approved_at': '2026-10-20T06:00:00+00:00', 'revision': 1}
    pending = {**approved, 'rule_id': 'CK-04', 'review_status': 'pending', 'approved': False}
    with tempfile.TemporaryDirectory() as temp:
        store = Path(temp) / 'review.json'
        store.write_text(json.dumps({'items': {'CK-03': approved, 'CK-04': pending}}, ensure_ascii=False), encoding='utf-8')
        initial = store.read_bytes()
        def run(val, **kwargs):
            return handoff_confirmed_ck(val, store=store, **kwargs)
        valid = {'rule_id': 'CK-03', 'judgment_confirmed': True, 'evidence_ref': 'TEST-JUDGMENT-001'}
        check('판정 입력 없음 차단', run(None)['status'] == '판정 입력 없음')
        check('후보 미전달 차단', run({'judgment_confirmed': True, 'evidence_ref': 'X'})['proposal'] is None)
        check('기준표 밖 CK 차단', run({**valid, 'rule_id': 'CK-99'})['proposal'] is None)
        check('잠정 후보 차단', run({**valid, 'judgment_confirmed': False})['status'] == '판정 미확정')
        check('판정 상태 누락 차단', run({'rule_id': 'CK-03', 'evidence_ref': 'X'})['proposal'] is None)
        check('근거 참조 누락 차단', run({**valid, 'evidence_ref': None})['status'] == '판정 근거 식별자 누락')
        check('공백 근거 차단', run({**valid, 'evidence_ref': '  '})['proposal'] is None)
        check('미승인 문장 차단', run({**valid, 'rule_id': 'CK-04'})['status'] == '승인된 문장 없음')
        success = run(valid, confirmed_department='시험 부서', confirmed_legal_basis='시험 조문')
        check('확정 CK 승인 문장 연결', success['status'] == '승인 문장 연결됨' and success['proposal']['action_proposal_sentence'] == sentence)
        check('확인된 부서·근거 전달', success['proposal']['ready_for_full_display'] is True)
        check('부서·조문 누락 상태 유지', run(valid)['proposal']['ready_for_full_display'] is False)
        check('연결 처리 후 원본 저장소 불변', store.read_bytes() == initial)
        samples = json.loads((ROOT / 'data' / 'RADAR_AI10_민원샘플_정리_v2.json').read_text(encoding='utf-8-sig'))['records']
        check('22건 원본 입력 수 일치', len(samples) == 22)
        outcomes = [run({'rule_id': rec.get('ck_candidate'), 'judgment_confirmed': False, 'evidence_ref': None}) for rec in samples]
        check('22건 잠정 후보 확정 처리 방지', all(item['proposal'] is None for item in outcomes))
    print(f'결과: {ok}/{ok} 통과 | 실제 Gemini/DB 호출 없음')

if __name__ == '__main__':
    main()
