"""A-10 DAT-06 저장본 비교. PUBLIC_REAL에 놓고 실행.
--test는 가상 경계값 검사. 기본 실행은 이미 저장된 두 실제 응답만 읽습니다.
신규 API 호출·DB 변경·자동 재계산·반기 실행 등록 없음.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
from html import escape
import json
from pathlib import Path, PurePosixPath
import sys
import unittest

TARGETS=[('DAT-06','보행자전용도로'),('DAT-07','횡단보도'),('DAT-08','어린이보호구역'),('DAT-09','노인·장애인보호구역'),('DAT-10','경찰청 보호구역')]
JOB_ID='job_20261022_184134_2bbff5'


def compare(old,new):
    for part in (old,new):
        if part['data_id']!='DAT-06' or part['filters']!={'signguNm':'성남시'}:
            raise ValueError('dataset_or_scope_mismatch')
        time=datetime.fromisoformat(part['collected_at'])
        if time.tzinfo is None:raise ValueError('timezone_required')
    if datetime.fromisoformat(new['collected_at'])<datetime.fromisoformat(old['collected_at']):
        raise ValueError('collection_order_reversed')
    if old['endpoint']!=new['endpoint']:
        raise ValueError('endpoint_mismatch')
    same_date=old['basis_dates']==new['basis_dates']
    same_count=old['received_rows']==new['received_rows']
    same_content=old['content_sha256']==new['content_sha256']
    if same_date and same_count and same_content:
        status='저장본 간 변경 없음';review=False
    elif same_date:
        status='기준일 같음·건수 또는 내용 변경';review=True
    else:
        status='기준일 변경·내용 검토 필요';review=True
    return dict(data_id='DAT-06',status=status,same_basis_dates=same_date,
                same_row_count=same_count,same_content_ignoring_order=same_content,
                old_rows=old['received_rows'],new_rows=new['received_rows'],
                old_basis_dates=old['basis_dates'],new_basis_dates=new['basis_dates'],
                old_collected_at=old['collected_at'],new_collected_at=new['collected_at'],
                operator_review_required=review,live_provider_checked=False,
                semiannual_check_completed=False,db_written=False,recalculated=False,
                note='저장된 두 응답만 비교. 제공처 현재 갱신 여부·성남 전체 시설 수·반기 운영 실행 완료를 뜻하지 않음.')


def read_snapshot(folder,verify_collection):
    evidence=verify_collection(folder)
    manifest=json.loads((folder/'collection.json').read_text(encoding='utf-8-sig'))
    signatures=[]
    for name in manifest['pages']:
        data=json.loads((folder/name).read_text(encoding='utf-8-sig'))
        body=data.get('response',data)['body'];items=body['items']
        if isinstance(items,dict):items=items.get('item',[])
        if isinstance(items,dict):items=[items]
        signatures.extend(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':')) for row in items)
    # Sorting ignores item/page order but preserves every original row and count.
    canonical=json.dumps(sorted(signatures),ensure_ascii=False,separators=(',',':')).encode('utf-8')
    evidence['content_sha256']=hashlib.sha256(canonical).hexdigest()
    return evidence


def render(report):
    def t(v):return escape(str(v))
    r=report['comparison']
    body=[]
    for data_id,name in TARGETS:
        values=[data_id,name,r['status'] if data_id=='DAT-06' else '비교 기록 없음',
                '이번 저장본 비교 수행' if data_id=='DAT-06' else '이번 실행에서 미확인']
        body.append('<tr>'+''.join('<td>'+t(x)+'</td>' for x in values)+'</tr>')
    checks=[('자료 기준일',', '.join(r['old_basis_dates']),', '.join(r['new_basis_dates'])),
            ('행 수',r['old_rows'],r['new_rows']),('수집 시각(기록의 시간대)',r['old_collected_at'],r['new_collected_at'])]
    detail=''.join('<tr>'+''.join('<td>'+t(v)+'</td>' for v in row)+'</tr>' for row in checks)
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-10 실제 저장본 비교</title>
<style>body{font-family:'Malgun Gothic',sans-serif;margin:28px;color:#17263c;line-height:1.7}h1{font-size:26px}h2{font-size:19px}.notice{background:#fff3d6;padding:16px}.result{background:#eaf5ef;padding:16px;margin:18px 0}table{border-collapse:collapse;font-size:14px;margin:14px 0}th,td{border:1px solid #ccd4df;padding:10px;vertical-align:top}th{background:#e9eff7}.scroll{overflow:auto}</style>
<h1>A-10 실제 저장본 비교</h1><div class="notice">같은 날 수집한 DAT-06의 두 실제 저장본으로 비교 동작을 확인합니다. 반기가 지난 자료를 비교하거나 제공처의 현재 갱신일을 조회한 결과는 아닙니다. 다른 네 종류는 미확인으로 남깁니다.</div>
<div class="result">DAT-06 결과: '''+t(r['status'])+'<br>행·페이지 순서를 제외한 내용 동일: '+t(r['same_content_ignoring_order'])+'<br>운영자 검토 필요: '+t(r['operator_review_required'])+'''</div>
<h2>DAT-06 비교 근거</h2><div class="scroll"><table><tr><th>항목</th><th>첫 수집</th><th>두 번째 수집</th></tr>'''+detail+'''</table></div>
<h2>A-10 대상별 확인 상태</h2><table><tr><th>자료 번호</th><th>자료</th><th>결과</th><th>실행 범위</th></tr>'''+''.join(body)+'''</table>
<p>내용은 JSON 행을 정규화한 뒤 순서와 무관하게 비교합니다. 원문 파일은 수정하지 않습니다. 기준일이 같아도 내용이 다르면 ‘변경 없음’으로 처리하지 않습니다.</p><p>새 수집·DB 변경·자동 재계산·순위 확정·정기 실행 등록 없음. 실제 반기 확인 일정과 제공처 변경 정보 연결은 별도 작업입니다.</p></html>'''


class ChangeTests(unittest.TestCase):
    def sample(self):
        return dict(data_id='DAT-06',filters={'signguNm':'성남시'},endpoint='same',
                    collected_at='2026-10-22T15:00:00+00:00',basis_dates=['2026-05-12'],
                    received_rows=407,content_sha256='same-content')
    def test_unchanged(self):
        r=compare(self.sample(),self.sample())
        self.assertEqual(r['status'],'저장본 간 변경 없음');self.assertFalse(r['semiannual_check_completed'])
    def test_changed_date(self):
        a=self.sample();b=self.sample();b['basis_dates']=['2026-06-01']
        self.assertTrue(compare(a,b)['operator_review_required'])
    def test_same_date_changed_content(self):
        a=self.sample();b=self.sample();b['content_sha256']='different'
        self.assertEqual(compare(a,b)['status'],'기준일 같음·건수 또는 내용 변경')
    def test_changed_count(self):
        a=self.sample();b=self.sample();b['received_rows']=408
        self.assertTrue(compare(a,b)['operator_review_required'])
    def test_scope_mismatch(self):
        a=self.sample();b=self.sample();b['filters']={'signguNm':'다른시'}
        with self.assertRaises(ValueError):compare(a,b)
    def test_reverse_time(self):
        a=self.sample();b=self.sample();b['collected_at']='2026-10-21T15:00:00+00:00'
        with self.assertRaises(ValueError):compare(a,b)
    def test_endpoint_mismatch(self):
        a=self.sample();b=self.sample();b['endpoint']='different'
        with self.assertRaises(ValueError):compare(a,b)
    def test_four_unchecked(self):
        html=render({'comparison':compare(self.sample(),self.sample())})
        self.assertEqual(html.count('비교 기록 없음'),4)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true');args=parser.parse_args()
    if args.test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(ChangeTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    public=Path(__file__).resolve().parent
    common=public.parent if (public.parent/'run_a01_all.py').is_file() else public.parents[1]/'I07_LLM_TEST/AXI_RADAR_2.0_2026-feature-w05-llm'
    sys.path.insert(0,str(common))
    from run_a01_evidence import verify_collection
    old=read_snapshot(common/'outputs/a01_api/DAT-06',verify_collection)
    job_folder=public/'outputs/a02_jobs'/JOB_ID
    job=json.loads((job_folder/'job.json').read_text(encoding='utf-8-sig'))
    if job.get('status')!='success' or job.get('data_id')!='DAT-06':raise ValueError('수집 성공 기록 확인 필요')
    relative=PurePosixPath(job['collection_record'])
    if relative.is_absolute() or '..' in relative.parts or relative.name!='collection.json':raise ValueError('수집 기록 경로 확인 필요')
    new=read_snapshot(job_folder/Path(*relative.parts).parent,verify_collection)
    report=dict(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),comparison=compare(old,new),
                target_count=5,compared_count=1,unchecked_count=4,
                old_file_sha256=old['sha256'],new_file_sha256=new['sha256'])
    output=public/'outputs/a10_real';output.mkdir(parents=True,exist_ok=True)
    (output/'changes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'changes.html').write_text(render(report),encoding='utf-8')
    r=report['comparison']
    print('DAT-06:',r['status'])
    print('첫 수집:',r['old_rows'],'건 / 두 번째 수집:',r['new_rows'],'건')
    print('기준일 같음:',r['same_basis_dates'],'/ 순서를 제외한 내용 같음:',r['same_content_ignoring_order'])
    print('비교 확인: 1종 / 미확인: 4종 / 반기 운영 확인 완료 아님')
    print('화면:',output/'changes.html')
    return 0


if __name__=='__main__':
    sys.exit(main())
