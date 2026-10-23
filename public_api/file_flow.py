"""Local review of public, processed team CSVs. No DB or external AI calls."""
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from uuid import uuid4

ALLOWED = {'DAT-06', 'DAT-07', 'DAT-11', 'DAT-12'}
LIMIT = 20 * 1024 * 1024

def digest(data):
    return hashlib.sha256(data).hexdigest()

def validate(data, profile):
    """A-05: draft header/date/key/numeric checks; never edits row values."""
    issues = []
    def issue(row, column, code):
        issues.append(dict(row_number=row, column=column, code=code))
    try:
        reader = csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
        header = next(reader, None)
        rows = list(reader)
    except (UnicodeError, csv.Error):
        return dict(total_rows=None, completed=False, issues=[dict(row_number=None,column=None,code='invalid_utf8_csv')], basis_dates=[])
    if not header or len(header) != len(set(header)) or set(header) != set(profile['columns']):
        return dict(total_rows=len(rows), completed=False, issues=[dict(row_number=1,column=None,code='header_mismatch')], basis_dates=[])
    seen = {}; keys = {}; dates = set()
    for number, row in enumerate(rows, 2):
        if len(row) != len(header):
            issue(number, None, 'column_count'); continue
        signature = tuple(row)
        if signature in seen: issue(number, None, 'duplicate_row')
        else: seen[signature] = number
        item = dict(zip(header, row))
        key = item[profile['key_column']].strip()
        if not key: issue(number, profile['key_column'], 'required_empty')
        elif key in keys: issue(number, profile['key_column'], 'duplicate_key_review')
        else: keys[key] = number
        raw = item[profile['date_column']].strip()
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw): raise ValueError()
            date.fromisoformat(raw); dates.add(raw)
        except ValueError: issue(number, profile['date_column'], 'invalid_or_missing_date')
        for column in profile['decimal_columns']:
            raw = item[column].strip()
            if not raw: continue  # optional absence is not changed to zero
            try:
                if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', raw) or not Decimal(raw).is_finite():
                    raise ValueError()
            except (ValueError, InvalidOperation): issue(number, column, 'invalid_decimal')
    if not rows: issue(None, None, 'empty_dataset_review')
    return dict(total_rows=len(rows), completed=True, issues=issues, basis_dates=sorted(dates))

def process(source, profile, root, run_id):
    if profile.get('data_id') not in ALLOWED or profile.get('original_status') != '가공본':
        raise ValueError('only_selected_processed_public_data')
    for field in ('source','operator','date_column','key_column'):
        if not isinstance(profile.get(field), str) or not profile[field].strip(): raise ValueError('missing_metadata')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', run_id): raise ValueError('invalid_run_id')
    path = Path(source)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != '.csv': raise ValueError('regular_csv_required')
    if path.stat().st_size > LIMIT: raise ValueError('file_too_large')
    data = path.read_bytes()
    if len(data) > LIMIT: raise ValueError('file_too_large')
    # Strictly a copy of the RECEIVED processed file; not an assertion of original provenance.
    folder = Path(root) / run_id / profile['data_id'] / uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=False)
    archived = folder / 'received.csv'
    with archived.open('xb') as handle: handle.write(data)
    saved = archived.read_bytes()
    if digest(saved) != digest(data): raise RuntimeError('archive_hash_mismatch')
    result = validate(saved, profile)
    result.update(data_id=profile['data_id'],name=profile['name'],source=profile['source'],
        provider=profile.get('provider'),original_status='가공본',
        original_collected_date=profile.get('original_collected_date'),
        received_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        operator=profile['operator'],operator_authenticated=False,run_id=run_id,
        sha256=digest(data),archived_file='received.csv',
        archive_matches_received=True,source_unchanged=digest(path.read_bytes())==digest(data),
        issue_count=len(result['issues']),profile_approval=profile.get('profile_approval'),
        latest_status='미확인',db_written=False,approved_for_scoring=False,
        validation_scope='CSV 제목·필수 식별키·기준일·일부 숫자 형식·중복. 전체 필수칸/자료 의미/좌표 범위 검사는 미확정.')
    (folder/'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),encoding='utf8')
    return folder, result

def render(results):
    def e(v): return escape('미확인' if v is None else str(v))
    fields=['data_id','name','total_rows','basis_dates','original_status','original_collected_date','issue_count','latest_status']
    labels=['자료 ID','자료명','행 수','파일에 기록된 기준일','원본 확인','원천 수집일','검토 항목 수','최신 여부']
    rows=''.join('<tr>'+''.join('<td>'+e(r[k])+'</td>' for k in fields)+'</tr>' for r in results)
    detail=''
    for r in results:
        detail+='<h2>'+e(r['data_id'])+' 검사 항목</h2>'
        detail+='<p>검사 범위: '+e(r['validation_scope'])+'</p>'
        detail+='<table><tr><th>CSV 행 번호</th><th>칸</th><th>검토 코드</th></tr>'
        detail+=''.join('<tr><td>'+e(i['row_number'])+'</td><td>'+e(i['column'])+'</td><td>'+e(i['code'])+'</td></tr>' for i in r['issues'])+'</table>'
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>실제 공공자료 파일 검사</title><style>body{font-family:Malgun Gothic,sans-serif;margin:32px;line-height:1.7;color:#183044}table{border-collapse:collapse}td,th{padding:10px;border:1px solid #ccd5dd}th{background:#edf2f7}.scroll{overflow:auto}</style><h1>실제 공공자료 파일 검사</h1><p>팀 DB용 가공본 4종을 읽고 받은 파일 그대로 별도 보관했습니다. 제공기관 원본을 새로 수집한 결과가 아닙니다.</p><p>원천 수집일과 최신판 여부는 미확인입니다. 검사 규칙은 초안이며, 검사 항목 0건도 산정 사용 승인을 뜻하지 않습니다. 운영자 표시는 로컬 입력값이며 로그인 연결은 없습니다. 민원 원본·수치지형도는 포함하지 않았습니다.</p><div class="scroll"><table><tr>'+''.join('<th>'+e(t)+'</th>' for t in labels)+'</tr>'+rows+'</table></div>'+detail+'</html>'
