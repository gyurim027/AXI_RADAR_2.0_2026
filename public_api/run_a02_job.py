"""A-02 DAT-06 수집 실행 기록 및 운영자 확인 요청.
api_collect.py 옆에 놓습니다. --test는 임시 가상 응답 검사만 실행합니다.
--collect만 실제 API를 호출합니다. 실패 후 --retry-of 실행번호로 새 수집을 시작합니다.
정기 스케줄러·공통 알림 발송·DB 저장은 아직 연결하지 않습니다.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from api_collect import collect, network

SAFE_ERRORS = {'retry_exhausted','total_changed_during_collection','page_count_mismatch',
               'duplicate_items_review','page_limit_reached','invalid_api_response',
               'response_too_large','http_access_failed','collection_failed'}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run_job(output_root, key, retry_of=None, fetch=network, pause=None):
    output_root = Path(output_root)
    if retry_of is not None:
        if not re.fullmatch(r'job_[0-9]{8}_[0-9]{6}_[a-f0-9]{6}', retry_of):
            raise ValueError('invalid_retry_id')
        parent = json.loads((output_root / retry_of / 'job.json').read_text(encoding='utf-8'))
        if parent.get('data_id') != 'DAT-06' or parent.get('status') not in {'failed','review_required','configuration_error'}:
            raise ValueError('retry_parent_not_retryable')
    started = datetime.now(timezone.utc)
    run_id = 'job_'+started.strftime('%Y%m%d_%H%M%S_')+uuid4().hex[:6]
    folder = output_root / run_id
    folder.mkdir(parents=True, exist_ok=False)
    report = dict(job_id=run_id, data_id='DAT-06', retry_of=retry_of,
                  filters={'signguNm':'성남시'}, started_at=started.isoformat(),
                  status='running', received_rows=0, expected_total=None,
                  collection_record=None, operator_review_required=True,
                  notification_sent=False, db_written=False, scheduled=False,
                  restart_policy='이전 원문 보존. 1페이지부터 새로 수집; 이어받기 아님.')
    if not isinstance(key, str) or not key.strip():
        report.update(status='configuration_error', error_code='api_key_required')
    else:
        try:
            options = {'fetch':fetch}
            if pause is not None:
                options['pause'] = pause
            raw_folder, result = collect('DAT-06', {'signguNm':'성남시'}, key.strip(), folder, **options)
            complete = result.get('complete') is True
            review = result.get('operator_review_required') is not False
            code = result.get('error_code')
            report.update(
                status='success' if complete and not review else ('review_required' if complete else 'failed'),
                received_rows=result.get('received_rows',0), expected_total=result.get('total_count'),
                collection_record=(raw_folder / 'collection.json').relative_to(folder).as_posix(),
                operator_review_required=not (complete and not review),
                error_code=code if code in SAFE_ERRORS else ('collection_failed' if not complete else None))
        except Exception:
            # Never include exception text, request URL, API key, or raw provider errors.
            report.update(status='failed', error_code='unexpected_collection_error')
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_json(folder/'job.json', report)
    if report['operator_review_required']:
        write_json(folder/'operator_review.json', dict(
            job_id=run_id, data_id='DAT-06', status='pending',
            reason=report.get('error_code') or 'review_required',
            received_rows=report['received_rows'], expected_total=report['expected_total'],
            notification_sent=False, notification_integration='공통 I-03 연결 전; 확인 요청 파일만 저장',
            raw_content_included=False))
    return folder, report


def response(page, total=101):
    size=100
    return json.dumps({'header':{'resultCode':'00'},'body':{
        'pageNo':page,'numOfRows':size,'totalCount':total,
        'items':{'item':[{'id':str(i)} for i in range((page-1)*size,min(page*size,total))]}}}).encode('utf-8')


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_success(self):
        from urllib.parse import urlparse,parse_qs
        fetch=lambda url:response(int(parse_qs(urlparse(url).query)['pageNo'][0]))
        folder,r=run_job(self.root,'TEST_SECRET',fetch=fetch,pause=lambda _:None)
        self.assertEqual((r['status'],r['received_rows']),('success',101))
        self.assertFalse((folder/'operator_review.json').exists())
        self.assertNotIn('TEST_SECRET',(folder/'job.json').read_text(encoding='utf-8'))
    def test_retry_exhausted_retains_first_page(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if len(calls)==1:return response(1)
            raise TimeoutError('TEST_SECRET')
        folder,r=run_job(self.root,'TEST_SECRET',fetch=fetch,pause=lambda _:None)
        self.assertEqual((r['status'],r['received_rows'],r['error_code']),('failed',100,'retry_exhausted'))
        self.assertEqual(len(calls),4)
        self.assertEqual(len(list(folder.rglob('page_*.json'))),1)
        self.assertTrue((folder/'operator_review.json').exists())
    def test_missing_key_no_network(self):
        def fetch(_):raise AssertionError('must not call')
        folder,r=run_job(self.root,None,fetch=fetch)
        self.assertEqual(r['status'],'configuration_error')
        self.assertIsNone(r['collection_record'])
    def test_new_run_keeps_parent(self):
        folder,old=run_job(self.root,None)
        before=(folder/'job.json').read_bytes()
        new,r=run_job(self.root,None,retry_of=old['job_id'])
        self.assertNotEqual(new,folder)
        self.assertEqual((folder/'job.json').read_bytes(),before)
        self.assertEqual(r['retry_of'],old['job_id'])
    def test_zero_requires_review(self):
        folder,r=run_job(self.root,'TEST_SECRET',fetch=lambda _:response(1,0))
        self.assertEqual(r['status'],'review_required')
        self.assertTrue((folder/'operator_review.json').exists())
    def test_exception_text_not_logged(self):
        def fetch(_):raise RuntimeError('TEST_SECRET')
        folder,r=run_job(self.root,'TEST_SECRET',fetch=fetch)
        self.assertEqual(r['error_code'],'unexpected_collection_error')
        for p in folder.rglob('*.json'):
            self.assertNotIn('TEST_SECRET',p.read_text(encoding='utf-8'))
    def test_invalid_retry_blocked(self):
        with self.assertRaises(ValueError):run_job(self.root,None,retry_of='../other')


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--test',action='store_true')
    mode.add_argument('--collect',action='store_true')
    parser.add_argument('--retry-of')
    args=parser.parse_args()
    if args.test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(JobTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    try:
        folder,result=run_job(Path(__file__).resolve().parent/'outputs/a02_jobs',
                              os.environ.get('RADAR_DATA_GO_KR_KEY'),retry_of=args.retry_of)
    except (OSError,ValueError,TypeError):
        print('재실행 번호 또는 이전 실행 기록을 확인해 주세요.')
        return 2
    print('실행 번호:',result['job_id'])
    print('결과:',result['status'],'/ 받은 행:',result['received_rows'])
    print('운영자 확인:',result['operator_review_required'])
    print('기록:',folder/'job.json')
    print('정기 자동 실행·알림 발송·DB 저장은 아직 연결하지 않았습니다.')
    return 0 if result['status']=='success' else 1


if __name__=='__main__':
    sys.exit(main())
