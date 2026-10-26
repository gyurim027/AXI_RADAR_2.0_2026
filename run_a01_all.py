"""A-01: DAT-06 API 원문 1종 + A-03~05 가공 CSV 8종의 검증 기록 연결.
uv run python run_a01_all.py --run r_1023_021317_a4b8d0
DB 접속·수정·외부 통신 없음. 같은 폴더의 앞선 세 프로그램을 사용합니다.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from run_a01_scope import make_catalog
from run_a01_evidence import verify_collection, read_json
from run_a03_real_flow import PROFILES, inspect_csv


def verify_files(folder):
    summary = read_json(folder / 'summary.json')
    expected = {p['data_id']: p for p in PROFILES}
    if not isinstance(summary, list) or len(summary) != len(expected):
        raise ValueError('CSV 연결 기록이 8개가 아닙니다.')
    found = {}
    for record in summary:
        key = record.get('data_id')
        if key not in expected or key in found:
            raise ValueError('CSV 자료 번호가 중복되거나 다릅니다.')
        profile = expected[key]
        receipt = read_json(folder / key / 'receipt.json')
        if receipt != record or record.get('input_name') != profile['file'] or record.get('source_id') != profile['source_id']:
            raise ValueError('접수 기록과 요약이 다릅니다.')
        archived = folder / key / 'received.csv'
        if archived.is_symlink() or not archived.is_file() or archived.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('보관 파일을 확인해 주세요.')
        raw = archived.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record.get('sha256'):
            raise ValueError('보관 파일의 내용이 접수 기록과 다릅니다.')
        result = inspect_csv(raw, profile)
        if result != record.get('validation') or result != read_json(folder / key / 'validation.json'):
            raise ValueError('재검사 결과와 저장된 검사 기록이 다릅니다.')
        if record.get('original_status') != '가공본' or record.get('run_id') != folder.name:
            raise ValueError('가공본 상태 또는 실행 번호가 다릅니다.')
        if result['basis_values'] != record.get('basis_values'):
            raise ValueError('원문의 기준일과 접수 기록이 다릅니다.')
        if record.get('archive_matches_input') is not True or record.get('source_unchanged') is not True:
            raise ValueError('접수 당시 원문 일치 확인이 없습니다.')
        found[key] = dict(kind='가공 CSV', rows=result['total_rows'], basis=result['basis_values'],
                          original_status='가공본', received_at=record['received_at'], original_collected_at=None,
                          issues=result['issue_count'], basis_precision=record['basis_precision'],
                          sha256=record['sha256'], archive_status='보관 파일 내용·검사 기록 재확인',
                          receipt_status=record['receipt_status'], latest_status='판정 보류')
    return found


def connect(root, run_name):
    if not re.fullmatch(r'r_[0-9]{4}_[0-9]{6}_[a-f0-9]{6}', run_name):
        raise ValueError('실행 번호 형식을 확인해 주세요.')
    catalog = make_catalog(read_json(root / 'outputs/a01_db/source_list.json'))
    api = verify_collection(root / 'outputs/a01_api/DAT-06')
    evidence = verify_files(root / 'outputs/a03_flow' / run_name)
    if 'DAT-06' in evidence:
        raise ValueError('중복 자료 번호')
    evidence['DAT-06'] = dict(kind='실제 API 응답', rows=api['received_rows'], basis=api['basis_dates'],
                             original_status='API 응답 원문', received_at=api['collected_at'],
                             original_collected_at=api['collected_at'], issues=None, basis_precision='일',
                             sha256=api['sha256'], archive_status='저장된 페이지 내용 재확인',
                             receipt_status='API 수집 기록 확인', latest_status='판정 보류')
    for item in catalog['items']:
        item['verified_evidence'] = evidence.get(item['data_id'])
        if item['verified_evidence']:
            ev = item['verified_evidence']
            item.update(availability='저장된 실제 파일 확인', original_status=ev['original_status'],
                        original_collected_at=ev['original_collected_at'], latest_status='판정 보류')
    catalog.update(connected_count=len(evidence), csv_run=run_name,
                   evidence_checked_at=datetime.now(timezone.utc).isoformat(),
                   all_files_verified=False, team_approved=False, db_written=False)
    return catalog


def render(catalog):
    def t(value):
        return escape('미확인' if value is None else str(value))
    headers=['DAT 번호','자료 이름','SRC 번호','실제 파일確認'.replace('確認',' 확인'),'확인 행 수','원문의 날짜·연도 범위','원본 상태','수집·로컬 접수 시각','검토 항목','최신 여부','확인 범위']
    rows=[]
    for item in catalog['items']:
        ev=item['verified_evidence']
        if ev:
            dates=ev['basis']
            period=(dates[0]+' ~ '+dates[-1]) if len(dates)>1 else (dates[0] if dates else None)
            checks='API 페이지·건수·지역·기준일 확인' if item['data_id']=='DAT-06' else '가공 CSV 접수·보관·부분 검사 재확인'
            count=ev['issues'] if ev['issues'] is not None else 'CSV 검사 대상 아님'
            values=[item['data_id'],item['name'],item['source_id'],ev['kind'],ev['rows'],period,ev['original_status'],ev['received_at'],count,'판정 보류',checks]
        else:
            values=[item['data_id'],item['name'],item['source_id'],'이번 연결에서 미확인',None,None,'미확인',None,None,'판정 보류',item['mapping_note']]
        rows.append('<tr'+(' class="verified"' if ev else '')+'>'+''.join('<td>'+t(v)+'</td>' for v in values)+'</tr>')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-01 실제 자료 연결 목록</title>
<style>body{font-family:'Malgun Gothic',sans-serif;margin:28px;color:#17263c;line-height:1.7}h1{font-size:26px}.notice{background:#fff3d6;padding:16px}.summary{background:#eaf5ef;padding:16px;margin:18px 0}.scroll{overflow:auto;max-height:70vh}table{border-collapse:collapse;font-size:14px}th,td{border:1px solid #ccd4df;padding:10px;min-width:120px;vertical-align:top}th{position:sticky;top:0;background:#e9eff7}td:nth-child(2),td:last-child{min-width:220px}.verified{background:#eaf5ef}</style>
<h1>A-01 실제 자료 연결 목록</h1><div class="summary">기준 목록 34종 중 저장된 실제 파일 확인 9종: API 응답 원문 1종 + 팀 가공 CSV 8종.</div>
<div class="notice">‘이번 연결에서 미확인’은 미수집 또는 파일 없음 판정이 아닙니다. 출처 목록은 저장된 DB 기록이며 실시간 조회가 아닙니다. 가공 CSV의 접수 시각은 이번 로컬 실행 시각으로, 제공기관 원본 수집일과 다릅니다. 모든 항목의 최신 여부는 판정 보류입니다. 팀 서버·로그인·운영 회차·DB 저장·최종 검사 규칙·A-06 공간 검사는 별도 확인이 필요합니다.</div>
<p>연두색 행은 저장된 파일과 기록을 다시 확인한 자료입니다. 검토 항목 0건은 정해 둔 부분 검사에서 발견된 항목이 없다는 뜻입니다. 자료 대응표는 팀 검토안입니다.</p>
<div class="scroll"><table><tr>'''+''.join('<th>'+t(h)+'</th>' for h in headers)+'</tr>'+''.join(rows)+'</table></div><p>CSV 실행 번호: '+t(catalog['csv_run'])+'</p><p>DB 및 입력 파일 수정 없음. JSON에는 실제 파일 확인 결과·검사 범위·SHA-256 확인값을 함께 보관합니다.</p></html>'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True,help='앞서 성공한 A-03~A-05 실행 번호')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    try:
        catalog=connect(root,args.run)
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        raise SystemExit('목록 연결 중단: 입력 파일·보관 기록을 확인해 주세요. ('+type(exc).__name__+')')
    output=root/'outputs/a01_all'
    output.mkdir(parents=True,exist_ok=True)
    (output/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'catalog.html').write_text(render(catalog),encoding='utf-8')
    print('기준 목록:',len(catalog['items']),'종 / 실제 파일 연결:',catalog['connected_count'],'종')
    print('API 원문 1종 + 실제 가공 CSV 8종 / DB 수정 없음')
    print('화면:',output/'catalog.html')


if __name__=='__main__':
    main()
