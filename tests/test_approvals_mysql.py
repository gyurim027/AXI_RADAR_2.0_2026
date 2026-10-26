"""별도 로컬 MySQL/MariaDB의 격리 DB에서 실제 SQL·행 잠금을 시험한다.

기본 실행에서는 건너뛴다. RADAR_I07_MYSQL_TEST=1과 RADAR_I07_TEST_USER 필요.
매 시험 radar_i07_test_<무작위> DB를 생성·삭제한다. 공용 RADAR_DB_*를 사용하지 않는다.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import access_audit as audit, db
from app.core.config import DbSettings, get_settings
from app.main import app
from test_approvals_api import headers, submit

pytestmark = pytest.mark.skipif(os.getenv('RADAR_I07_MYSQL_TEST') != '1',
                                reason='격리 MySQL 시험은 명시적 환경 설정 후 실행')


@pytest.fixture
def mysql_env(monkeypatch):
    import pymysql
    from pymysql.cursors import DictCursor
    user = os.environ['RADAR_I07_TEST_USER']
    host = os.getenv('RADAR_I07_TEST_HOST', '127.0.0.1')
    # 공용 원격 DB를 향한 실수 방지. 이 시험은 로컬 전용이다.
    assert host in ('127.0.0.1', 'localhost', '::1')
    port = int(os.getenv('RADAR_I07_TEST_PORT', '3306'))
    socket = os.getenv('RADAR_I07_TEST_SOCKET')
    password = os.getenv('RADAR_I07_TEST_PASSWORD', '')
    name = 'radar_i07_test_' + uuid4().hex
    kwargs = dict(user=user, password=password, cursorclass=DictCursor, charset='utf8mb4', autocommit=False)
    kwargs.update(unix_socket=socket) if socket else kwargs.update(host=host, port=port)
    admin = pymysql.connect(**kwargs)
    previous_store = audit.get_store()
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        admin.commit()
        settings = replace(get_settings(), db=DbSettings(host, port, user, password, name, socket))
        monkeypatch.setattr(db, 'get_settings', lambda: settings)
        audit.set_store(audit.AuditStore())
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute('CREATE TABLE app_user (user_id BIGINT PRIMARY KEY) ENGINE=InnoDB')
                cur.execute('INSERT INTO app_user VALUES (7),(22)')
                for table in ['62', '70', '87', '88']:
                    cur.execute((Path(__file__).parent/'fixtures'/'i07'/f'{table}.sql').read_text())
                cur.execute("INSERT INTO jurisdiction (jurisdiction_id, problem) VALUES ('JUR-01','보도 파손')")
                cur.execute("INSERT INTO jurisdiction_dept (jurisdiction_id,sort_no,gu_name,dept_name,org_level) "
                            "VALUES ('JUR-01',1,'수정구','건설과','구')")
                for pid, after in [(1,'중원구: 보도관리팀'),(2,'분당구: 보도팀')]:
                    cur.execute("INSERT INTO setting_version (setting_version_id,setting_kind,content_ref,"
                                "proposed_by,proposed_at,approval_status) VALUES (%s,'담당 부서 표',%s,7,NOW(),'제안')",
                                (pid,f'JUR-01 보도 파손: 수정구: 건설과 → {after} (근거 별표 1)'))
            con.commit()
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        audit.set_store(previous_store)
        with admin.cursor() as cur:
            # name은 외부 입력을 포함하지 않고 이 fixture가 생성한 값이다.
            cur.execute(f'DROP DATABASE IF EXISTS `{name}`')
        admin.commit()
        admin.close()


def execute(sql, args=()):
    with db.connect() as con:
        with con.cursor() as cur:
            cur.execute(sql, args)
        con.commit()


def one(sql, args=()):
    return db.read_only(sql, args)[0]


def test_mysql_actual_apply_and_idempotent_retry(mysql_env):
    c = mysql_env
    assert submit(c,1).status_code == 200
    assert one('SELECT setting_version_id FROM jurisdiction')['setting_version_id'] == 1
    assert one('SELECT dept_name FROM jurisdiction_dept')['dept_name'] == '보도관리팀'
    assert c.post('/api/approvals/1/apply',headers=headers()).json()['application']['alreadyApplied'] is True
    assert one('SELECT COUNT(*) AS n FROM access_audit')['n'] == 1


def test_mysql_same_proposal_concurrent_reviews(mysql_env):
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: submit(mysql_env,1).status_code,[1,2]))
    assert sorted(statuses) == [200,409]
    assert one('SELECT COUNT(*) AS n FROM access_audit')['n'] == 1


@pytest.mark.parametrize('iteration', range(3))
def test_mysql_different_proposals_same_jurisdiction(mysql_env, iteration):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda pid: submit(mysql_env,pid),[1,2]))
    assert sorted(r.status_code for r in responses) == [200,409]
    assert next(r for r in responses if r.status_code == 409).json()['error']['code'] == 'table_changed'
    assert one('SELECT COUNT(*) AS n FROM setting_version WHERE approval_status=%s',('승인',))['n'] == 2
    assert one('SELECT COUNT(*) AS n FROM access_audit')['n'] == 2


def test_mysql_audit_failure_rolls_back_approval(mysql_env):
    execute("CREATE TRIGGER fail_audit BEFORE INSERT ON access_audit FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test audit failure'")
    assert submit(mysql_env,1).status_code == 500
    assert one('SELECT approval_status FROM setting_version WHERE setting_version_id=1')['approval_status'] == '제안'
    assert one('SELECT dept_name FROM jurisdiction_dept')['dept_name'] == '건설과'


def test_mysql_apply_failure_preserves_approval_then_retry(mysql_env):
    execute("CREATE TRIGGER fail_dept BEFORE INSERT ON jurisdiction_dept FOR EACH ROW "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='test apply failure'")
    assert submit(mysql_env,1).status_code == 503
    assert one('SELECT approval_status FROM setting_version WHERE setting_version_id=1')['approval_status'] == '승인'
    assert one('SELECT dept_name FROM jurisdiction_dept')['dept_name'] == '건설과'
    assert one('SELECT setting_version_id FROM jurisdiction')['setting_version_id'] is None
    execute('DROP TRIGGER fail_dept')
    assert mysql_env.post('/api/approvals/1/apply',headers=headers()).status_code == 200
    assert one('SELECT COUNT(*) AS n FROM access_audit')['n'] == 1


def test_mysql_max_comment_length_and_reject(mysql_env):
    assert submit(mysql_env,1,'돌려보냄','가'*255).status_code == 200
    assert one('SELECT CHAR_LENGTH(review_comment) AS n FROM setting_version WHERE setting_version_id=1')['n'] == 255
    assert one('SELECT access_reason FROM access_audit')['access_reason'] == '돌려보냄'
