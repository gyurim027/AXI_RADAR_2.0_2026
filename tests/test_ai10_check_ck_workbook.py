"""AD-13 엑셀 검증기 자체 시험: 기준 엑셀은 절대 수정하지 않음."""
import argparse
import copy
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().with_name('ai10_check_ck_workbook.py')
spec = importlib.util.spec_from_file_location('ai10_ck_check', MODULE)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reference', type=Path, required=True)
    args = p.parse_args()
    src = check.read_table(args.reference)
    count = 0

    def ok(name, condition):
        nonlocal count
        assert condition, name
        count += 1
        print('통과 |', name)

    base = check.compare(src, src)
    ok('원본 14건 인식', base['reference_count'] == base['candidate_count'] == 14)
    ok('원본 구조 검사 통과', not base['candidate_errors'])
    ok('원본과 비교 시 변경 0건', not base['changes'])
    ok('원본 G열 빈 문장 허용', any('공란' in x for x in base['candidate_warnings']))

    edited = copy.deepcopy(src)
    edited['G2'] = '운영자가 검토한 시험 문장'
    output = check.compare(src, edited)
    ok('문장 변경 감지', any(x.get('ck') == 'CK-01' and x.get('column') == 'G' for x in output['changes']))
    ok('문장 변경만으로 구조 오류 미발생', not output['candidate_errors'])

    bad = copy.deepcopy(src)
    bad['C2'] = ''
    ok('필수 확인 항목 누락 차단', any('C2' in e for e in check.compare(src, bad)['candidate_errors']))

    dup = copy.deepcopy(src)
    dup['A3'] = 'CK-01'
    result = check.compare(src, dup)
    ok('CK 중복 번호 차단', any('중복' in e for e in result['candidate_errors']))

    header = copy.deepcopy(src)
    header['G1'] = '임의 변경'
    ok('머리글 임의 변경 차단', any('G1' in e for e in check.compare(src, header)['candidate_errors']))

    removed = copy.deepcopy(src)
    removed['A2'] = ''
    ok('CK 삭제 비교 감지', any(x['ck'] == 'CK-01' and x['type'] == '삭제' for x in check.compare(src, removed)['changes']))

    added = copy.deepcopy(src)
    for col, val in zip(check.COLS, [src.get(f'{c}2','') for c in check.COLS]):
        added[f'{col}16'] = val
    added['A16'] = 'CK-15'
    ok('신규 CK 항목 추가 감지', any(x['ck'] == 'CK-15' and x['type'] == '추가' for x in check.compare(src, added)['changes']))

    ok('검사 중 기준 데이터 불변', src == check.read_table(args.reference))
    print(f'결과: {count}/{count} 통과 | 원본 엑셀 변경 없음')


if __name__ == '__main__':
    main()
