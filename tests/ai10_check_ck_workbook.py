"""AD-13 / 05_03 조치 제안 표: 읽기 전용 구조·변경 검증.

Python 표준 라이브러리만 사용합니다. 원본이나 후보 엑셀을 수정하지 않습니다.
실행 예:
  uv run python tests/ai10_check_ck_workbook.py --reference "원본.xlsx" --candidate "수정본.xlsx"
"""
import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

SHEET = '05_03.조치 제안 표'
COLS = 'ABCDEFGHIJKLM'
HEADERS = [
    '항목 ID', '판정 결과 종류', '확인 항목', '데이터로 모르는 이유',
    '확인할 것 (MVP 포함)', '조치 종류', '조치 제안 문장 (AI-10 초안 작성 후 채움)',
    '현장 입력 항목 (확장 단계)', '관할 ID',
    '받는 부서 (05 관할 매핑의 1차 해결 부서)', '근거 상태',
    '근거 조문 찾을 곳 (후보)', '비고',
]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
CK = re.compile(r'^CK-\d{2,}$')
CELL = re.compile(r'^([A-Z]+)(\d+)$')


def read_table(path):
    """표준 xlsx의 대상 시트 값만 읽기 (수식은 저장된 캐시값 기준)."""
    with zipfile.ZipFile(path) as archive:
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        rel_map = {node.attrib['Id']: node.attrib['Target'] for node in rels}
        entry = next((e for e in book.findall('s:sheets/s:sheet', NS) if e.attrib['name'] == SHEET), None)
        if entry is None:
            raise ValueError(f'필요한 시트 없음: {SHEET}')
        relid = entry.attrib[f'{{{NS["r"]}}}id']
        target = rel_map[relid].lstrip('/')
        sheet_path = target if target.startswith('xl/') else f'xl/{target}'
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            doc = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join((n.text or '') for n in si.findall('.//s:t', NS))
                       for si in doc.findall('s:si', NS)]
        doc = ET.fromstring(archive.read(sheet_path))
        cells = {}
        for c in doc.findall('.//s:sheetData/s:row/s:c', NS):
            addr = c.attrib.get('r', '')
            match = CELL.match(addr)
            if not match:
                continue
            v = c.find('s:v', NS)
            inline = c.find('s:is', NS)
            if c.attrib.get('t') == 's' and v is not None:
                value = strings[int(v.text)]
            elif c.attrib.get('t') == 'inlineStr' and inline is not None:
                value = ''.join(t.text or '' for t in inline.findall('.//s:t', NS))
            elif v is not None:
                value = v.text or ''
            else:
                value = ''
            cells[addr] = value
        return cells


def rows_from_cells(cells):
    rows = {}
    for n in range(2, max((int(CELL.match(c).group(2)) for c in cells if CELL.match(c)), default=1) + 1):
        values = {col: (cells.get(f'{col}{n}', '') or '').strip() for col in COLS}
        if CK.match(values['A']):
            rows.setdefault(values['A'], []).append((n, values))
        elif values['A'].startswith('CK-') or (any(values[c] for c in COLS[1:]) and n <= 15):
            rows.setdefault(f'!행{n}', []).append((n, values))
    return rows


def validate(cells):
    errors, warnings = [], []
    for col, header in zip(COLS, HEADERS):
        value = (cells.get(f'{col}1', '') or '').strip()
        if value != header:
            errors.append(f'{col}1 머리글 불일치: 예상={header!r}, 실제={value!r}')
    rows = rows_from_cells(cells)
    for key, entries in rows.items():
        if len(entries) != 1:
            errors.append(f'{key}: CK 번호 중복 ({len(entries)}건)')
        for n, values in entries:
            if not CK.match(values['A']):
                errors.append(f'A{n}: CK 형식 오류 ({values["A"]!r})')
            for col in ('B', 'C', 'D', 'E', 'F', 'I', 'J', 'K', 'L'):
                if not values[col]:
                    errors.append(f'{col}{n}: 원본 필수 정보 누락')
            if not values['G']:
                warnings.append(f'G{n}: 조치 제안 문장 공란 (초안 작성 전에는 허용)')
            if values['J'] in ('근거 없음', '확인 필요') or values['K'] in ('근거 없음', '확인 필요'):
                warnings.append(f'{key}: 받는 부서 또는 근거 상태에 추가 확인 필요')
    if not any(CK.match(k) for k in rows):
        errors.append('유효한 CK 항목 없음')
    return rows, errors, warnings


def compare(reference, candidate):
    ref_rows, ref_err, ref_warn = validate(reference)
    new_rows, new_err, new_warn = validate(candidate)
    changes = []
    for key in sorted(set(ref_rows) | set(new_rows)):
        old = ref_rows.get(key, [])
        new = new_rows.get(key, [])
        if not old:
            changes.append({'ck': key, 'type': '추가'})
        elif not new:
            changes.append({'ck': key, 'type': '삭제'})
        elif len(old) == len(new) == 1:
            for col in COLS:
                a, b = old[0][1][col], new[0][1][col]
                if a != b:
                    changes.append({'ck': key, 'column': col, 'header': HEADERS[COLS.index(col)],
                                    'type': '변경', 'before': a, 'after': b})
    return {'sheet': SHEET, 'reference_count': sum(len(v) for v in ref_rows.values()),
            'candidate_count': sum(len(v) for v in new_rows.values()),
            'reference_errors': ref_err, 'candidate_errors': new_err,
            'candidate_warnings': new_warn, 'changes': changes,
            'result': '검사 실패' if new_err else '구조 검사 통과 (변경 내용은 운영자 확인 필요)',
            'notice': '읽기 전용 검사입니다. 변경 내용 승인 또는 원본 적용을 수행하지 않습니다.'}


def main():
    parser = argparse.ArgumentParser(description='RADAR AD-13 05_03 파일 수정 전 읽기 전용 검증')
    parser.add_argument('--reference', required=True, type=Path, help='기준 통합 대장 .xlsx')
    parser.add_argument('--candidate', required=True, type=Path, help='수정 후보 통합 대장 .xlsx')
    parser.add_argument('--report', type=Path, help='선택: 검사 결과 JSON 저장 경로')
    args = parser.parse_args()
    try:
        result = compare(read_table(args.reference), read_table(args.candidate))
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        print(f'검사 불가능: {exc}', file=sys.stderr)
        return 2
    print(f"대상 시트: {result['sheet']} | 기준 {result['reference_count']}건 / 후보 {result['candidate_count']}건")
    print(f"구조 오류: {len(result['candidate_errors'])}건 / 검토 알림: {len(result['candidate_warnings'])}건 / 변경: {len(result['changes'])}건")
    for e in result['candidate_errors']:
        print('오류 |', e)
    for w in result['candidate_warnings']:
        print('알림 |', w)
    for c in result['changes']:
        print('변경 |', c.get('ck'), c.get('column',''), c['type'],
              repr(c.get('before','')), '=>', repr(c.get('after','')))
    print(result['result'])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('검사 보고서:', args.report)
    return 1 if result['candidate_errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
