"""A-01: 저장된 출처 목록과 DAT-06 API 원문을 읽어 확인 결과를 표시합니다.
공통 프로젝트 루트에서 uv run python run_a01_evidence.py
DB·네트워크 접속 없음. 원문 수정 없음. 입력은 outputs/a01_api/DAT-06.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from run_a01_scope import make_catalog

ENDPOINT = 'https://api.data.go.kr/openapi/tn_pubr_public_pedestrian_road_api'


def read_json(path):
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('파일 크기를 확인해 주세요.')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def verify_collection(folder):
    manifest_path = folder / 'collection.json'
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError('수집 기록 형식 오류')
    if manifest.get('data_id') != 'DAT-06' or manifest.get('endpoint') != ENDPOINT:
        raise ValueError('DAT-06의 지정된 API 수집 기록이 아닙니다.')
    if manifest.get('complete') is not True or manifest.get('error_code'):
        raise ValueError('완료되지 않은 수집 기록입니다.')
    if manifest.get('filters', {}).get('signguNm') != '성남시':
        raise ValueError('성남시 필터를 확인해 주세요.')
    total = manifest.get('total_count')
    if type(total) is not int or total <= 0 or type(manifest.get('received_rows')) is not int or manifest['received_rows'] != total:
        raise ValueError('전체 건수와 받은 건수가 일치하지 않습니다.')
    stamp = manifest.get('received_at')
    if not isinstance(stamp, str):
        raise ValueError('수집 시각이 없습니다.')
    collected_at = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if collected_at.tzinfo is None:
        raise ValueError('수집 시각의 시간대가 없습니다.')
    pages = manifest.get('pages')
    expected_pages = (total + 99) // 100
    if not isinstance(pages, list) or len(pages) != expected_pages or len(set(pages)) != len(pages):
        raise ValueError('페이지 수 또는 중복 페이지를 확인해 주세요.')
    rows = []
    hashes = {'collection.json': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    for number, name in enumerate(pages, 1):
        if name != f'page_{number:04d}.json':
            raise ValueError('페이지 이름 또는 순서가 다릅니다.')
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('페이지 파일이 없거나 일반 파일이 아닙니다.')
        content = read_json(path)
        response = content.get('response', content)
        if str(response['header']['resultCode']) not in ('00', '0'):
            raise ValueError('API 정상 응답 코드가 아닙니다.')
        body = response['body']
        if int(body['totalCount']) != total or int(body['pageNo']) != number or int(body['numOfRows']) != 100:
            raise ValueError('API 페이지 정보가 일치하지 않습니다.')
        items = body.get('items')
        if isinstance(items, dict):
            items = items.get('item', [])
            if isinstance(items, dict):
                items = [items]
        expected = min(100, total - (number - 1) * 100)
        if not isinstance(items, list) or len(items) != expected or not all(isinstance(r, dict) for r in items):
            raise ValueError('페이지의 실제 행 수가 일치하지 않습니다.')
        rows.extend(items)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(rows) != total:
        raise ValueError('원문의 총 행 수가 다릅니다.')
    signatures = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows]
    if len(set(signatures)) != total:
        raise ValueError('내용이 완전히 같은 중복 행이 있습니다. 임의 삭제하지 않습니다.')
    dates = set()
    for row in rows:
        if str(row.get('signguNm') or '').strip() != '성남시':
            raise ValueError('성남시 이외 또는 지역 빈칸이 있습니다.')
        value = str(row.get('referenceDate') or '').strip()
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('자료 기준일 형식을 확인해 주세요.')
        dates.add(value)
    return dict(
        data_id='DAT-06', received_rows=total, saved_pages=len(pages), basis_dates=sorted(dates),
        collected_at=collected_at.isoformat(), original_status='API 응답 원문',
        endpoint=ENDPOINT, filters={'signguNm': '성남시'}, sha256=hashes,
        check_scope='응답 코드·페이지 순서·건수·동일 행 중복·성남시 표기·기준일 형식',
        latest_status='판정 보류', team_approved=False, db_written=False,
    )


def render_catalog(catalog, evidence):
    def text(v):
        return escape('미확인' if v is None else str(v))
    heads = ['DAT 번호', '자료 이름', 'SRC 번호', '출처 대응', '실제 자료 확인', '확인 행 수', '실제 자료 기준일', 'API 수집 시각', '원본 상태', '최신 여부', '대장 기준일·기간', '대장 갱신 주기', '확인할 점']
    body = []
    for item in catalog['items']:
        actual = item['data_id'] == 'DAT-06'
        values = [item['data_id'], item['name'], item['source_id'], item['status'],
                  '저장된 API 원문 확인' if actual else '미확인',
                  evidence['received_rows'] if actual else None,
                  ', '.join(evidence['basis_dates']) if actual else None,
                  evidence['collected_at'] if actual else None,
                  evidence['original_status'] if actual else '미확인',
                  '판정 보류', item['document_basis'], item['cycle'],
                  ('최신판·좌표 정확도·실제 시설 수·팀 승인·DB 저장은 확인하지 않았습니다. ' if actual else '') + item['mapping_note']]
        body.append('<tr' + (' class="checked"' if actual else '') + '>' + ''.join('<td>'+text(v)+'</td>' for v in values) + '</tr>')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-01 실제 수집 기록 연결</title>
<style>body{font-family:'Malgun Gothic',sans-serif;color:#17263c;margin:28px;line-height:1.7}h1{font-size:26px}.notice{background:#fff4d9;padding:16px}.summary{background:#eaf5ef;padding:16px;margin:18px 0}.scroll{overflow:auto;max-height:70vh}table{border-collapse:collapse;font-size:14px}td,th{padding:10px;border:1px solid #ccd4df;min-width:125px;vertical-align:top}th{position:sticky;top:0;background:#e9eff7}td:nth-child(2),td:last-child{min-width:245px}.checked{background:#eaf5ef}</style>
<h1>A-01 실제 수집 기록 연결</h1>
<div class="notice">기준 목록 34개와 저장된 DB 출처 목록을 대조한 검토안입니다. 출처 등록과 실제 파일 확보를 구분합니다. 이번 화면은 실시간 DB 조회가 아닙니다. 최신 여부와 팀 승인은 확정하지 않습니다.</div>
<div class="summary">DAT-06 실제 API 원문 확인: ''' + text(evidence['received_rows']) + '건 / '+text(evidence['saved_pages'])+'페이지<br>자료 기준일: '+text(', '.join(evidence['basis_dates']))+'<br>API 수집 시각: '+text(evidence['collected_at'])+'''<br>수집 시각과 자료 기준일은 서로 다릅니다. 나머지 항목의 ‘미확인’은 자료가 없다는 뜻이 아닙니다.</div>
<p>연두색 DAT-06 행에 실제 수집 기록을 표시했습니다. ‘대장 기준일’은 문서의 기록이며 실제 파일의 날짜와 구분합니다.</p>
<div class="scroll"><table><thead><tr>''' + ''.join('<th>'+text(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div><p>검사 범위: '+text(evidence['check_scope'])+'</p><p>DB·API·원본 파일 수정 없음. 원문의 SHA-256 확인값은 catalog.json에 기록합니다. 이 확인값은 이번 실행 시점의 파일을 식별하며 최초 수집 이후 변조가 없었다는 증명은 아닙니다.</p></html>'


def main():
    root = Path(__file__).resolve().parent
    try:
        sources = read_json(root / 'outputs/a01_db/source_list.json')
        result = make_catalog(sources)
        evidence = verify_collection(root / 'outputs/a01_api/DAT-06')
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SystemExit('연결 확인 중단: 입력 파일과 형식을 확인해 주세요. ('+type(exc).__name__+')')
    result['verified_collection'] = evidence
    for item in result['items']:
        if item['data_id'] == 'DAT-06':
            item.update(availability='저장된 API 원문 확인', original_status=evidence['original_status'],
                        original_collected_at=evidence['collected_at'], verified_rows=evidence['received_rows'],
                        verified_basis_dates=evidence['basis_dates'], latest_status='판정 보류')
    output = root / 'outputs/a01_evidence'
    output.mkdir(parents=True, exist_ok=True)
    (output/'catalog.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (output/'catalog.html').write_text(render_catalog(result,evidence), encoding='utf-8')
    print('DAT-06 실제 원문 확인:', evidence['received_rows'], '건 /', evidence['saved_pages'], '페이지')
    print('자료 기준일:', ', '.join(evidence['basis_dates']))
    print('DB 수정 없음 / 최신 여부·팀 승인 미확정')
    print('화면:', output/'catalog.html')


if __name__ == '__main__':
    main()
