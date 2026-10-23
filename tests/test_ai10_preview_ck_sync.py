"""AD-13 읽기 전용 엑셀/JSON 대조 시험: 기준 엑셀 필요.
실행: uv run python tests/test_ai10_preview_ck_sync.py --reference "data/원본.xlsx"
"""
import argparse
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai10_check_ck_workbook as check
from ai10_preview_ck_sync import preview


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    ref = check.read_table(args.reference)
    rows, errors, _ = check.validate(ref)
    assert not errors, errors
    store = {'items': {rid: {'edited_template': f'기존 {rid} 문장', 'review_status': 'pending', 'approved': False} for rid in rows}}
    snap_ref, snap_store = copy.deepcopy(ref), copy.deepcopy(store)
    count = 0
    def ok(name, cond):
        nonlocal count
        assert cond, name
        count += 1
        print('통과 |', name)
    same = preview(ref, ref, store)
    ok('원본 읽기 및 미리보기', not same['errors'] and len(same['sentence_comparison']) == 14)
    ok('기준 엑셀 변경 없음', ref == snap_ref)
    ok('검토 저장소 변경 없음', store == snap_store)
    ok('빈 G열은 적용 제외', any(x['result'] == '빈 문장: 적용 대상 제외' for x in same['sentence_comparison']))
    ck = 'CK-01'
    row = rows[ck][0][0]
    changed = dict(ref)
    changed[f'G{row}'] = '운영자가 입력한 조치 문장'
    diff = preview(ref, changed, store)
    result = next(x for x in diff['sentence_comparison'] if x['ck'] == ck)
    ok('수정된 문장 차이 감지', result['result'] == '문장 차이: 운영자 확인 필요')
    ok('원본 대비 엑셀 변경 감지', any(x.get('ck') == ck and x.get('column') == 'G' for x in diff['workbook_changes']))
    approved = copy.deepcopy(store)
    approved['items'][ck]['approved'] = True
    approved['items'][ck]['review_status'] = 'approved'
    result2 = next(x for x in preview(ref, changed, approved)['sentence_comparison'] if x['ck'] == ck)
    ok('승인 문장 무단 교체 경고', result2['result'].startswith('기존 승인 상태'))
    deleted = dict(ref)
    deleted[f'A{row}'] = ''
    ok('CK 누락 차단', bool(preview(ref, deleted, store)['errors']))
    header = dict(ref)
    header['G1'] = '임의 이름'
    ok('머리글 변경 차단', bool(preview(ref, header, store)['errors']))
    missing = copy.deepcopy(store)
    missing['items'].pop(ck)
    ok('JSON CK 목록 불일치 차단', bool(preview(ref, ref, missing)['errors']))
    ok('시험 도중 실제 파일 쓰기 없음', ref == snap_ref and store == snap_store)
    print(f'결과: {count}/{count} 통과 | 원본 엑셀 및 JSON 변경 없음')

if __name__ == '__main__':
    main()
