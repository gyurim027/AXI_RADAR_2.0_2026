"""22건 샘플과 공식 판정 CSV의 명시적 시설ID 연결만 검사한다.

명시적 링크는 외부에서 확인된 자료를 뜻하며, CK 후보는 확정 판정으로 승격하지 않는다.
샘플 설명/제목/gid 유사성으로 매칭하지 않는다. API/DB/Gemini/승인 저장소 호출 없음.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any
from .ai10_assessment_ck_match import match_assessment_ck

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / 'data' / 'RADAR_AI10_민원샘플_정리_v2.json'
ID_FIELDS = {
    '07_assess_crosswalk': '횡단보도관리번호',
    '08_assess_sidewalk': 'UFID',
    '09_assess_intersection': '교차로ID',
    '10_assess_zone': '보호구역ID',
}


def check_22_assessment_links(records: list[dict[str, Any]], links: dict[str, Any],
                              tables: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """확인된 sample_id -> 테이블·시설 고유번호·출처 참조 링크에 대해서만 후보를 반환."""
    if not isinstance(records, list) or not isinstance(links, dict):
        raise ValueError('샘플 목록과 연결표의 형식이 잘못됐습니다')
    ids = [r.get('sample_id') for r in records]
    if any(not isinstance(s, str) or not s.strip() for s in ids) or len(set(ids)) != len(ids):
        raise ValueError('샘플 ID 누락/중복')
    unknown = set(links) - set(ids)
    if unknown:
        raise ValueError('존재하지 않는 샘플 ID: '+', '.join(sorted(unknown)))
    indexes: dict[str, dict[str, list[dict[str, str]]]] = {}
    for table, key in ID_FIELDS.items():
        idx: dict[str, list[dict[str, str]]] = {}
        for row in tables.get(table, []):
            code = str(row.get(key) or '').strip()
            if code:
                idx.setdefault(code, []).append(row)
        indexes[table] = idx
    out = []
    for rec in records:
        sid = rec['sample_id']
        entry = links.get(sid)
        base = {'sample_id': sid, 'confirmed_rule_id': None, 'ck_candidates': [],
                'judgment_confirmed': False, 'gemini_invoked': False}
        if entry is None:
            out.append({**base, 'status': '시설 식별자 연결 미제공'})
            continue
        if not isinstance(entry, dict):
            out.append({**base, 'status': '연결표 형식 오류'})
            continue
        table = entry.get('table')
        fid = entry.get('facility_id')
        evidence = entry.get('evidence_ref')
        if table not in ID_FIELDS or not isinstance(fid, str) or not fid.strip() or not isinstance(evidence, str) or not evidence.strip():
            out.append({**base, 'status': '연결 근거 또는 시설 식별자 부족'})
            continue
        rows = indexes[table].get(fid.strip(), [])
        if len(rows) != 1:
            out.append({**base, 'status': '시설 레코드 없음' if not rows else '시설 식별자 중복',
                        'table': table, 'facility_id': fid.strip()})
            continue
        matched = match_assessment_ck(table, rows[0])
        out.append({**base, 'status': '대조 후보 있음 (미확정)' if matched['ck_candidates'] else '대조 후보 없음',
                    'table': table, 'facility_id': fid.strip(), 'evidence_ref': evidence.strip(),
                    'ck_candidates': matched['ck_candidates']})
    return {'counts': {'total':len(out), 'provided_links':len(links),
                       'candidate_records':sum(bool(r['ck_candidates']) for r in out),
                       'unlinked':sum(r['status']=='시설 식별자 연결 미제공' for r in out),
                       'confirmed':0}, 'records':out,
            'note':'시설 ID가 연결된 판정 레코드의 CK 후보만 검사; CK 확정·Gemini·DB 호출 없음'}


def load_csv_tables(zip_path: Path) -> dict[str, list[dict[str,str]]]:
    tables = {}
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for table in ID_FIELDS:
            candidates = [name for name in names if name.split('/')[-1] == table+'.csv']
            if len(candidates) != 1:
                raise ValueError(f'{table} CSV를 정확히 한 개 찾지 못했습니다')
            with z.open(candidates[0]) as f:
                tables[table] = list(csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig', newline='')))
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description='22건과 판정 CSV의 근거 있는 시설 ID 연결 확인')
    parser.add_argument('--csv-zip', required=True, type=Path, help='판정 CSV 84개 통합 ZIP')
    parser.add_argument('--links-json', type=Path, help='확인된 시설 식별자 연결표 (없으면 미연결 22건)')
    args = parser.parse_args()
    records = json.loads(SAMPLES.read_text(encoding='utf-8-sig'))['records']
    links = json.loads(args.links_json.read_text(encoding='utf-8-sig')) if args.links_json else {}
    result = check_22_assessment_links(records, links, load_csv_tables(args.csv_zip))
    for row in result['records']:
        print(f"{row['sample_id']} | {row['status']} | {','.join(c['rule_id'] for c in row['ck_candidates']) or '-'}")
    print(f"결과: {result['counts']['total']}건 / 연결표 {result['counts']['provided_links']}건 / CK 후보 {result['counts']['candidate_records']}건 / 확정 0건 | Gemini/DB 미호출")

if __name__ == '__main__':
    main()
