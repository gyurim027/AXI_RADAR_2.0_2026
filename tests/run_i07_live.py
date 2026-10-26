"""로컬 격리 MySQL/MariaDB + 실제 API + 기존 화면 DOM/Chromium 관통시험.

RADAR_I07_MYSQL_TEST=1, RADAR_I07_TEST_USER 필요. DOM은 RADAR_I07_DOM_RUNTIME,
--browser는 RADAR_I07_BROWSER_RUNTIME과 RADAR_I07_CHROMIUM_PATH를 사용한다.
공용 RADAR_DB_*는 사용하지 않는다. 시험 DB·계정은 생성 후 정리한다.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.error import HTTPError
from uuid import uuid4

import pymysql
from pymysql.cursors import DictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--browser', action='store_true', help='DOM 대신 설치된 Chrome/Chromium으로 실제 화면과 DB 연결 확인')
    parser.add_argument('--settings', action='store_true', help='I-02 운영자 조회 → I-07 시 승인 → 운영자 재조회 (--browser 필요)')
    args = parser.parse_args()
    if args.settings and not args.browser:
        raise RuntimeError('--settings는 --browser와 함께 실행하세요')
    if os.environ.get('RADAR_I07_MYSQL_TEST') != '1':
        raise RuntimeError('RADAR_I07_MYSQL_TEST=1을 명시해야 합니다')
    user = os.environ['RADAR_I07_TEST_USER']
    host = os.environ.get('RADAR_I07_TEST_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('별도 로컬 시험 인스턴스만 허용합니다')
    port = int(os.environ.get('RADAR_I07_TEST_PORT', '3306'))
    dom_runtime = os.environ.get('RADAR_I07_DOM_RUNTIME','')
    if not args.browser and not dom_runtime:
        raise RuntimeError('DOM 시험에는 RADAR_I07_DOM_RUNTIME이 필요합니다')
    if args.browser and not os.environ.get('RADAR_I07_CHROMIUM_PATH'):
        raise RuntimeError('브라우저 시험에는 RADAR_I07_CHROMIUM_PATH가 필요합니다')
    output = args.output_dir or Path(tempfile.mkdtemp(prefix='radar-i07-verification-'))
    output.mkdir(parents=True, exist_ok=True)
    name = 'radar_i07_test_ui_' + uuid4().hex
    fixture_password = secrets.token_urlsafe(20)
    fixture_login = 'i07_ui_' + uuid4().hex[:10]
    admin = pymysql.connect(host=host, port=port, user=user, password=os.environ.get('RADAR_I07_TEST_PASSWORD', ''),
                            charset='utf8mb4', cursorclass=DictCursor)
    api = None
    log = None
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        api_port = listener.getsockname()[1]
    base_url = f'http://127.0.0.1:{api_port}'

    def request(path, body=None, token=None, method=None, headers=None):
        h = {'Content-Type': 'application/json', **(headers or {})}
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(base_url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=h, method=method)
        return urllib.request.urlopen(req, timeout=5)

    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            cur.execute(f'USE `{name}`')
            for table in ['60_auth', '62', '70', '87', '88']:
                cur.execute((ROOT / 'tests/fixtures/i07' / f'{table}.sql').read_text(encoding='utf-8'))
            for uid, account, role in [(7, 'i07_ui_operator', 'RADAR 운영자'), (22, fixture_login, '시 도로과')]:
                cur.execute('INSERT INTO app_user (user_id,login_id,password_hash,display_name,org_name,team_name,role,is_active) '
                            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                            (uid, account, hash_password(fixture_password), '연동시험', '격리시험기관', '도로과', role, 'Y'))
            cur.execute("INSERT INTO jurisdiction (jurisdiction_id,problem) VALUES ('JUR-01','보도 파손')")
            cur.execute("INSERT INTO jurisdiction_dept (jurisdiction_id,sort_no,gu_name,dept_name,org_level) "
                        "VALUES ('JUR-01',1,'수정구','건설과','구')")
        admin.commit()
        api_env = {**os.environ, 'RADAR_DB_HOST': host, 'RADAR_DB_PORT': str(port), 'RADAR_DB_USER': user,
                   'RADAR_DB_PASSWORD': os.environ.get('RADAR_I07_TEST_PASSWORD', ''), 'RADAR_DB_NAME': name,
                   'RADAR_DB_SOCKET': '', 'RADAR_JWT_SECRET': secrets.token_urlsafe(40)}
        log = (output / 'api.log').open('w', encoding='utf-8')
        api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)],
                               cwd=ROOT, env=api_env, stdout=log, stderr=log)
        for _ in range(100):
            try:
                with request('/health') as response:
                    json.load(response)
                break
            except Exception:
                if api.poll() is not None:
                    raise RuntimeError('API 기동 실패. 출력 디렉터리의 api.log를 확인하세요')
                time.sleep(.1)
        else:
            raise RuntimeError('API 기동 시간 초과')
        with request('/api/auth/login', {'loginId': 'i07_ui_operator', 'password': fixture_password}) as response:
            token = json.load(response)['token']
        with request('/api/standards/drafts', {'jurId': 'JUR-01', 'problem': '보도 파손', 'from': '수정구: 건설과',
                                              'to': '중원구: 보도팀', 'basis': '별표 1'}, token=token) as response:
            draft = json.load(response)
        settings_checks = None
        if args.settings:
            with admin.cursor() as cur:
                cur.executemany("INSERT INTO setting_version (setting_version_id,setting_kind,version_label,content_ref,"
                                "proposed_by,proposed_at,approval_status) VALUES (%s,%s,'I02 연결 확인',%s,7,NOW(),'제안')",
                                [(2,'가중치','조회 검증용 설정 원문 또는 파일 위치'),
                                 (3,'기준값','같은 버전 이름의 다른 설정 번호')])
            admin.commit()
            with request('/api/settings/versions', token=token) as response:
                settings_checks = {'operator_list': json.load(response)}
            assert [r['settingVersionId'] for r in settings_checks['operator_list']['versions']] == [3,2]
            for path, expected in [('/api/approvals',403),('/api/settings/versions/999',404),('/api/settings/versions?status=invalid',422)]:
                try:
                    request(path,token=token)
                    raise AssertionError('권한·대상·필터 오류가 거부되지 않았습니다')
                except HTTPError as exc:
                    assert exc.code == expected
            with request('/api/auth/login', {'loginId': fixture_login,'password': fixture_password}) as response:
                city_token = json.load(response)['token']
            try:
                request('/api/settings/versions',token=city_token)
                raise AssertionError('승인자가 운영자 조회 API에 접근했습니다')
            except HTTPError as exc:
                assert exc.code == 403
            settings_checks['role_denials'] = {'operator_approval':403,'city_settings':403}
        with request('/api/approvals/1/review', method='OPTIONS', headers={
            'Origin': 'http://127.0.0.1:5173', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type',
        }) as response:
            cors = {'status': response.status, 'allow_origin': response.headers.get('access-control-allow-origin')}
            assert cors['allow_origin'] == 'http://127.0.0.1:5173'
        node_env = {**os.environ, 'RADAR_I07_DOM_RUNTIME': dom_runtime, 'RADAR_I07_LIVE_BASE': base_url,
                    'RADAR_I07_LIVE_ISOLATED': '1', 'RADAR_I07_LIVE_LOGIN': fixture_login,
                    'RADAR_I07_LIVE_PASSWORD': fixture_password}
        if args.browser:
            node_env['RADAR_I07_BROWSER_TEST']='1'
        if args.settings:
            node_env['RADAR_I02_BROWSER_TEST']='1'
        script = 'tests/i02-browser.test.mjs' if args.settings else 'tests/i07-browser.test.mjs' if args.browser else 'tests/i07-ui.test.mjs'
        result = subprocess.run(['node', '--test', '--test-force-exit', script], cwd=ROOT / 'frontend',
                                env=node_env, capture_output=True, text=True, encoding='utf-8')
        log_name = 'browser.log' if args.browser else 'dom.log'
        (output / log_name).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'화면 관통시험 실패. 출력 디렉터리의 {log_name}를 확인하세요')
        admin.rollback()
        with admin.cursor() as cur:
            snapshot = {}
            for table in ['setting_version', 'jurisdiction', 'jurisdiction_dept', 'access_audit']:
                cur.execute('SELECT * FROM ' + table)
                snapshot[table] = cur.fetchall()
            cur.execute('SELECT VERSION() AS version')
            version = cur.fetchone()['version']
        if args.settings:
            by_id = {r['setting_version_id']:r for r in snapshot['setting_version']}
            assert by_id[2]['approval_status'] == '승인' and by_id[2]['approved_by'] == 22
            assert by_id[1]['approval_status'] == '제안' and by_id[3]['approval_status'] == '제안'
            assert snapshot['jurisdiction'][0]['setting_version_id'] is None
            assert snapshot['jurisdiction_dept'][0]['dept_name'] == '건설과'
        else:
            assert snapshot['setting_version'][0]['approval_status'] == '승인'
            assert snapshot['setting_version'][0]['approved_by'] == 22
            assert snapshot['jurisdiction'][0]['setting_version_id'] == draft['settingVersionId']
            assert snapshot['jurisdiction_dept'][0]['dept_name'] == '보도팀'
        assert [r['resource_kind'] for r in snapshot['access_audit']].count('승인') == 1
        record = {'scope': ('Actual operator I02 → city I07 → operator reread, isolated DB; no department application or calculation' if args.settings else 'Actual Chromium frontend → live HTTP API → AI-05 function → isolated DB' if args.browser else 'Actual frontend DOM → live HTTP API → AI-05 function → isolated DB; no browser visual QA'),
                  'database_version': version, 'cors_preflight': cors, 'f05_created': draft, 'node_exit_code': result.returncode,
                  'final_state': snapshot, 'shared_db_used': False}
        if settings_checks is not None:
            record['settings_checks'] = settings_checks
        (output / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(f'PASS: {"I02 운영자 → I07 시 승인 → 운영자 재조회; 부서표 변경 없음" if args.settings else "F05 → 실제 로그인 UI → I07 → 87/88"} + 승인 감사 1건; 결과: {output}')
    finally:
        if api is not None:
            api.terminate()
            try:
                api.wait(timeout=10)
            except subprocess.TimeoutExpired:
                api.kill()
                api.wait()
        if log:
            log.close()
        try:
            admin.rollback()
            with admin.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS `{name}`')
            admin.commit()
        finally:
            admin.close()


if __name__ == '__main__':
    main()
