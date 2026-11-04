"""AD-13 / 05_03 수정 엑셀과 AI-10 검토 JSON의 읽기 전용 대조.

배치: tests/ai10_preview_ck_sync.py (동일 폴더의 ai10_check_ck_workbook.py 사용)
실행: uv run python tests/ai10_preview_ck_sync.py --reference "원본.xlsx" --candidate "수정본.xlsx" --store "data/ai10_operator_review_dev.json"
기존 파일을 수정하거나 승인하지 않습니다. --report 지정 시 별도의 미리보기 JSON만 생성합니다.
"""
import argparse
import json
import sys
from pathlib import Path

import ai10_check_ck_workbook as check


def preview(reference_cells, candidate_cells, store):
    comparison = check.compare(reference_cells, candidate_cells)
    reference_rows, _, _ = check.validate(reference_cells)
    candidate_rows, _, _ = check.validate(candidate_cells)
    items = store.get('items')
    if not isinstance(items, dict):
        raise ValueError('검토 저장소의 items 구조가 올바르지 않습니다.')
    expected = set(reference_rows)
    current = set(candidate_rows)
    stored = set(items)
    errors = list(comparison['reference_errors']) + list(comparison['candidate_errors'])
    if expected != current:
        errors.append('수정본에서 CK 번호가 추가·삭제되었습니다: ' + ', '.join(sorted(expected ^ current)))
    if expected != stored:
        errors.append('엑셀 원본과 JSON의 CK 번호가 다릅니다: ' + ', '.join(sorted(expected ^ stored)))
    if any(len(v) != 1 for v in candidate_rows.values()):
        errors.append('수정본 CK 번호 중복 또는 구조 이상')
    proposals = []
    if not errors:
        for rid in sorted(expected):
            original = reference_rows[rid][0][1]['G']
            proposed = candidate_rows[rid][0][1]['G']
            item = items[rid]
            existing = item.get('edited_template')
            if not isinstance(existing, str):
                errors.append(f'{rid}: JSON 검토 문장이 문자열이 아닙니다.')
                continue
            if not proposed:
                status = '빈 문장: 적용 대상 제외'
            elif proposed == existing:
                status = 'JSON 문장과 동일'
            elif item.get('approved') is True or item.get('review_status') == 'approved':
                status = '기존 승인 상태: 승인 취소·검토 없이 적용 금지'
            else:
                status = '문장 차이: 운영자 확인 필요'
            proposals.append({
                'ck': rid, 'original_excel_sentence': original,
                'candidate_excel_sentence': proposed,
                'current_json_sentence': existing,
                'json_review_status': item.get('review_status'),
                'json_approved': item.get('approved'),
                'result': status,
            })
    return {
        'result': '검사 실패' if errors else '미리보기 완료 (미적용)',
        'errors': errors,
        'workbook_changes': comparison['changes'],
        'workbook_warnings': comparison['candidate_warnings'],
        'sentence_comparison': proposals,
        'notice': '읽기 전용: 엑셀/JSON 덮어쓰기·문장 수정·자동 승인 없음. 변경 문장은 운영자 검토 후 별도 절차가 필요합니다.',
    }


def main():
    parser = argparse.ArgumentParser(description='AD-13 엑셀 ↔ 검토 저장소 변경 미리보기 (읽기 전용)')
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='선택: 별도 JSON 미리보기 출력 경로')
    args = parser.parse_args()
    try:
        ref = check.read_table(args.reference)
        cand = check.read_table(args.candidate)
        data = json.loads(args.store.read_text(encoding='utf-8-sig'))
        report = preview(ref, cand, data)
        print('판정:', report['result'])
        print('엑셀 변경:', len(report['workbook_changes']), '건 | 오류:', len(report['errors']), '건')
        for e in report['errors']:
            print('오류 |', e)
        for entry in report['sentence_comparison']:
            print(entry['ck'], '|', entry['result'])
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('미리보기 파일:', args.report)
        return 1 if report['errors'] else 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('검사 불가능:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
