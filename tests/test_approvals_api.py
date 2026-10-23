"""I-07 HTTP·SQL 전이·원자성 시험.

SQLite 시험 DB에서 저장소 실제 SQL을 실행한다. %s와 FOR UPDATE만 방언 변환한다.
MySQL FOR UPDATE 잠금·AI-05·87/88 연동 검증을 대체하지 않는다.
"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.core import access_audit as audit, db
from app.core.auth import make_token
from app.main import app


class Cursor:
    def __init__(self, con):
        self.cur = con.cursor()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.cur.close()
    def execute(self, sql, args=()):
        if sql == "START TRANSACTION READ ONLY":
            return
        self.cur.execute(sql.replace("%s", "?").replace(" FOR UPDATE", "").replace("NOW()", "CURRENT_TIMESTAMP"), args)
    def fetchone(self):
        row = self.cur.fetchone()
        return dict(row) if row else None
    def fetchall(self):
        return [dict(row) for row in self.cur.fetchall()]
    @property
    def lastrowid(self):
        return self.cur.lastrowid
    @property
    def rowcount(self):
        return self.cur.rowcount


class Connection:
    def __init__(self, con):
        self.con = con
    def cursor(self):
        return Cursor(self.con)
    def commit(self):
        self.con.commit()
    def rollback(self):
        self.con.rollback()


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = str(tmp_path / "review.sqlite")
    def raw():
        con = sqlite3.connect(path, timeout=10)
        con.row_factory = sqlite3.Row
        return con
    with raw() as con:
        con.executescript('''
        CREATE TABLE setting_version (
          setting_version_id INTEGER PRIMARY KEY, setting_kind TEXT, version_label TEXT,
          content_ref TEXT, proposed_by INTEGER, proposed_at TEXT,
          approval_status TEXT, approved_by INTEGER, approved_at TEXT, review_comment TEXT);
        CREATE TABLE jurisdiction (jurisdiction_id TEXT PRIMARY KEY, problem TEXT, setting_version_id INTEGER);
        CREATE TABLE jurisdiction_dept (jurisdiction_dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
          jurisdiction_id TEXT, sort_no INTEGER, gu_name TEXT, condition_text TEXT, dept_name TEXT, org_level TEXT);
        INSERT INTO jurisdiction VALUES ('JUR-01', '보도 파손', NULL);
        INSERT INTO jurisdiction_dept (jurisdiction_id,sort_no,gu_name,dept_name,org_level)
          VALUES ('JUR-01',1,'수정구','건설과','구');
        CREATE TABLE access_audit (actor_ref INTEGER, resource_kind TEXT, resource_key TEXT,
          client_ip TEXT, access_reason TEXT);
        ''')
        con.executemany("INSERT INTO setting_version VALUES (?, ?, 'v1', NULL, 7, '2026-10-23', ?, NULL, NULL, NULL)",
                        [(1, "담당 부서 표", "제안"), (2, "가중치", "제안"),
                         (3, "기준값", "승인"), (4, "알수없음", "제안"),
                         (5, "기준값", "제안"), (6, "우선 확인 조건", "제안")])
        con.execute("UPDATE setting_version SET content_ref=? WHERE setting_version_id=1",
                    ('JUR-01 보도 파손: 수정구: 건설과 → 중원구: 보도관리팀 (근거 별표 1)',))
    @contextmanager
    def connect():
        con = raw()
        try:
            # SQLite에만 적용되는 시험 직렬화. MySQL 행 잠금 증거는 아님.
            con.execute("BEGIN IMMEDIATE")
            yield Connection(con)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    def read_only(sql, args=()):
        with raw() as con:
            return [dict(r) for r in con.execute(sql.replace("%s", "?"), args)]
    monkeypatch.setattr(db, "connect", connect)
    monkeypatch.setattr(db, "read_only", read_only)
    previous = audit.get_store()
    audit.set_store(audit.AuditStore())
    client = TestClient(app, raise_server_exceptions=False)
    yield client, raw
    audit.set_store(previous)


def headers(role="city", uid=22):
    token, _ = make_token(dict(user_id=uid, login_id="reviewer", role=role, gu=None))
    return {"Authorization": f"Bearer {token}"}


def submit(c, pid, decision="승인", comment=None, role="city"):
    return c.post(f"/api/approvals/{pid}/review", headers=headers(role),
                  json={"decision": decision, "reviewComment": comment})


def state(raw, pid):
    with raw() as con:
        return dict(con.execute("SELECT * FROM setting_version WHERE setting_version_id=?", (pid,)).fetchone())


def audits(raw):
    with raw() as con:
        return [dict(r) for r in con.execute("SELECT * FROM access_audit")]


def test_list_and_detail(env):
    c, _ = env
    r = c.get("/api/approvals", headers=headers())
    assert r.status_code == 200
    assert [r['settingVersionId'] for r in r.json()['proposals']] == [1, 2, 4, 5, 6]
    assert c.get('/api/approvals/1', headers=headers()).json()['settingKind'] == '담당 부서 표'
    assert c.get('/api/approvals/999', headers=headers()).status_code == 404
    assert c.get('/api/approvals?status=임의', headers=headers()).status_code == 422


@pytest.mark.parametrize('role', ['district', 'operator'])
def test_wrong_role_has_no_writes(env, role):
    c, raw = env
    assert submit(c, 1, '돌려보냄', '수정', role).status_code == 403
    assert c.get('/api/approvals', headers=headers(role)).status_code == 403
    assert state(raw, 1)['approval_status'] == '제안'
    assert not audits(raw)


def test_login_required(env):
    c, _ = env
    assert c.get('/api/approvals').status_code == 401
    assert c.post('/api/approvals/1/review', json={'decision': '승인'}).status_code == 401


def test_reject_department_records_real_actor_and_audit(env):
    c, raw = env
    r = submit(c, 1, '돌려보냄', '  근거 원문을 보완해 주세요  ')
    assert r.status_code == 200
    assert r.json()['departmentApplied'] is False
    row = state(raw, 1)
    assert (row['approval_status'], row['approved_by'], row['review_comment']) == ('돌려보냄', 22, '근거 원문을 보완해 주세요')
    assert row['approved_at']
    log = audits(raw)
    assert len(log) == 1
    assert (log[0]['actor_ref'], log[0]['resource_kind'], log[0]['resource_key']) == (22, '승인', 'setting_version:1')
    assert log[0]['access_reason'] == '돌려보냄'


@pytest.mark.parametrize('pid', [2, 5, 6])
def test_approve_settings_without_recalculation(env, pid):
    c, raw = env
    r = submit(c, pid)
    assert r.status_code == 200
    assert r.json()['recalculationStarted'] is False
    assert state(raw, pid)['approval_status'] == '승인'
    assert len(audits(raw)) == 1


def test_department_approval_calls_actual_ai05_function(env):
    c, raw = env
    r = submit(c, 1)
    assert r.status_code == 200
    assert r.json()['departmentApplied'] is True
    assert r.json()['application']['alreadyApplied'] is False
    assert state(raw, 1)['approval_status'] == '승인'
    assert len(audits(raw)) == 1
    with raw() as con:
        assert con.execute("SELECT setting_version_id FROM jurisdiction").fetchone()[0] == 1
        row = con.execute("SELECT gu_name,dept_name FROM jurisdiction_dept").fetchone()
        assert tuple(row) == ('중원구','보도관리팀')


@pytest.mark.parametrize('comment', [None, '', '   '])
def test_reject_requires_reason(env, comment):
    c, raw = env
    assert submit(c, 1, '돌려보냄', comment).status_code == 422
    assert state(raw, 1)['approval_status'] == '제안'
    assert not audits(raw)


@pytest.mark.parametrize('payload', [
    {'decision': '승인', 'approved_by': 999},
    {'decision': '승인', 'userId': 999},
    {'decision': '확정'},
    {'decision': '돌려보냄', 'reviewComment': 'x' * 256},
])
def test_invalid_input_cannot_spoof_actor(env, payload):
    c, raw = env
    assert c.post('/api/approvals/2/review', headers=headers(), json=payload).status_code == 422
    assert state(raw, 2)['approval_status'] == '제안'
    assert not audits(raw)


@pytest.mark.parametrize('pid, status, code', [
    (999, 404, 'proposal_not_found'),
    (3, 409, 'proposal_already_reviewed'),
    (4, 422, 'unsupported_setting_kind'),
])
def test_target_errors(env, pid, status, code):
    c, raw = env
    r = submit(c, pid)
    assert (r.status_code, r.json()['error']['code']) == (status, code)
    assert not audits(raw)


def test_duplicate_decision_does_not_repeat_audit(env):
    c, raw = env
    assert submit(c, 2).status_code == 200
    assert submit(c, 2).status_code == 409
    assert len(audits(raw)) == 1


def test_audit_insert_failure_rolls_back_review(env):
    c, raw = env
    with raw() as con:
        con.execute("CREATE TRIGGER audit_fail BEFORE INSERT ON access_audit BEGIN SELECT RAISE(ABORT, 'audit failure'); END")
    assert submit(c, 2).status_code == 500
    row = state(raw, 2)
    assert row['approval_status'] == '제안'
    assert row['approved_by'] is None and row['approved_at'] is None
    assert not audits(raw)


def test_state_update_failure_rolls_back(env):
    c, raw = env
    with raw() as con:
        con.execute("CREATE TRIGGER update_fail BEFORE UPDATE ON setting_version BEGIN SELECT RAISE(ABORT, 'update failure'); END")
    assert submit(c, 2).status_code == 500
    assert state(raw, 2)['approval_status'] == '제안'
    assert not audits(raw)


def test_two_requests_sqlite_serialization_only(env):
    c, raw = env
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(c, 2).status_code, [1, 2]))
    assert sorted(results) == [200, 409]
    assert len(audits(raw)) == 1


def test_snake_response_option(env):
    c, _ = env
    r = c.get('/api/approvals/1', headers={**headers(), 'X-Response-Case': 'snake'})
    assert r.json()['setting_version_id'] == 1


def test_full_length_comment_preserved_without_overflowing_audit(env):
    c, raw = env
    comment = '가' * 255
    assert submit(c, 1, '돌려보냄', comment).status_code == 200
    assert state(raw, 1)['review_comment'] == comment
    assert audits(raw)[0]['access_reason'] == '돌려보냄'


@pytest.mark.parametrize('before,after,code,status', [
    ('수정구: 건설과', '각 구(확인 필요)', 'needs_review', 422),
    ('수정구: 건설과', '수정구: 건설과', 'no_change', 422),
    ('예전 표', '중원구: 보도관리팀', 'table_changed', 409),
])
def test_real_apply_errors_preserve_approved_state(env, before, after, code, status):
    c, raw = env
    with raw() as con:
        con.execute("UPDATE setting_version SET content_ref=? WHERE setting_version_id=1",
                    (f'JUR-01 보도 파손: {before} → {after} (근거 별표 1)',))
    r = submit(c, 1)
    assert (r.status_code, r.json()['error']['code']) == (status, code)
    assert r.json()['error']['approvalStatus'] == '승인'
    assert r.json()['error']['departmentApplied'] is False
    assert state(raw, 1)['approval_status'] == '승인'
    with raw() as con:
        assert con.execute("SELECT setting_version_id FROM jurisdiction").fetchone()[0] is None
        assert con.execute("SELECT dept_name FROM jurisdiction_dept").fetchone()[0] == '건설과'
    assert len(audits(raw)) == 1


def test_content_cut_preserves_actual_error(env):
    c, raw = env
    with raw() as con:
        con.execute("UPDATE setting_version SET content_ref=? WHERE setting_version_id=1",
                    ('JUR-01 보도 파손: 잘린 수정안…',))
    r = submit(c, 1)
    assert (r.status_code, r.json()['error']['code']) == (422, 'content_cut')
    assert state(raw, 1)['approval_status'] == '승인'


def test_apply_retry_idempotent_no_duplicate_approval_audit(env):
    c, raw = env
    assert submit(c, 1).status_code == 200
    with raw() as con:
        first_id = con.execute('SELECT jurisdiction_dept_id FROM jurisdiction_dept').fetchone()[0]
    r = c.post('/api/approvals/1/apply', headers=headers())
    assert r.status_code == 200 and r.json()['application']['alreadyApplied'] is True
    assert len(audits(raw)) == 1
    with raw() as con:
        assert con.execute('SELECT jurisdiction_dept_id FROM jurisdiction_dept').fetchone()[0] == first_id


def test_unapplied_preview_retry_routes(env):
    c, raw = env
    preview = c.get('/api/approvals/1/preview', headers=headers())
    assert preview.status_code == 200 and preview.json()['after'] == '중원구: 보도관리팀'
    assert state(raw, 1)['approval_status'] == '제안'
    assert not audits(raw)
    r = c.post('/api/approvals/1/apply', headers=headers())
    assert (r.status_code, r.json()['error']['code']) == (409, 'not_approved')
    with raw() as con:
        con.execute("UPDATE setting_version SET approval_status='승인' WHERE setting_version_id=1")
    pending = c.get('/api/approvals/unapplied', headers=headers()).json()['proposals']
    assert [r['settingVersionId'] for r in pending] == [1]
    assert c.post('/api/approvals/1/apply', headers=headers()).status_code == 200
    assert c.get('/api/approvals/unapplied', headers=headers()).json()['proposals'] == []


def test_apply_write_failure_keeps_approval_but_rolls_back_depts_then_retry(env):
    c, raw = env
    with raw() as con:
        con.execute("CREATE TRIGGER dept_fail BEFORE INSERT ON jurisdiction_dept BEGIN SELECT RAISE(ABORT, 'dept failure'); END")
    r = submit(c, 1)
    assert (r.status_code, r.json()['error']['code']) == (503, 'department_apply_failed')
    assert r.json()['error']['departmentApplied'] is None
    assert state(raw, 1)['approval_status'] == '승인'
    assert len(audits(raw)) == 1
    with raw() as con:
        assert con.execute('SELECT dept_name FROM jurisdiction_dept').fetchone()[0] == '건설과'
        assert con.execute('SELECT setting_version_id FROM jurisdiction').fetchone()[0] is None
        con.execute('DROP TRIGGER dept_fail')
    assert c.post('/api/approvals/1/apply', headers=headers()).status_code == 200
    assert len(audits(raw)) == 1


def test_audit_failure_prevents_department_application(env):
    c, raw = env
    with raw() as con:
        con.execute("CREATE TRIGGER audit_fail BEFORE INSERT ON access_audit BEGIN SELECT RAISE(ABORT, 'audit failure'); END")
    assert submit(c, 1).status_code == 500
    assert state(raw, 1)['approval_status'] == '제안'
    with raw() as con:
        assert con.execute('SELECT dept_name FROM jurisdiction_dept').fetchone()[0] == '건설과'
    assert not audits(raw)


@pytest.mark.parametrize('role', ['operator', 'district'])
def test_retry_and_preview_require_city(env, role):
    c, raw = env
    assert c.post('/api/approvals/1/apply', headers=headers(role)).status_code == 403
    assert c.get('/api/approvals/1/preview', headers=headers(role)).status_code == 403
    assert c.get('/api/approvals/unapplied', headers=headers(role)).status_code == 403
    assert not audits(raw)


def test_f05_submit_to_i07_approval_to_real_department_apply(env):
    c, raw = env
    r = c.post('/api/standards/drafts', headers=headers('operator', 7), json={
        'jurId': 'JUR-01', 'problem': '보도 파손', 'from': '수정구: 건설과',
        'to': '중원구: 보도관리팀', 'basis': '별표 1',
    })
    assert r.status_code == 200
    pid = r.json()['settingVersionId']
    assert state(raw, pid)['proposed_by'] == 7
    assert submit(c, pid).status_code == 200
    assert state(raw, pid)['approved_by'] == 22
    assert [r['resource_kind'] for r in audits(raw)] == ['설정 변경', '승인']
    with raw() as con:
        assert con.execute('SELECT setting_version_id FROM jurisdiction').fetchone()[0] == pid


def test_same_department_two_proposals_only_one_change(env):
    c, raw = env
    with raw() as con:
        con.execute("UPDATE setting_version SET setting_kind='담당 부서 표', content_ref=? WHERE setting_version_id=2",
                    ('JUR-01 보도 파손: 수정구: 건설과 → 분당구: 보도팀 (근거 별표 1)',))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pid: submit(c, pid), [1, 2]))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert next(r for r in results if r.status_code == 409).json()['error']['code'] == 'table_changed'
    assert state(raw, 1)['approval_status'] == state(raw, 2)['approval_status'] == '승인'
    assert len(audits(raw)) == 2


def test_unapproved_cannot_retry_even_if_version_pointer_matches(env):
    c, raw = env
    with raw() as con:
        con.execute('UPDATE jurisdiction SET setting_version_id=1')
    r = c.post('/api/approvals/1/apply', headers=headers())
    assert (r.status_code, r.json()['error']['code']) == (409, 'not_approved')


def test_blank_destination_cannot_delete_all_department_rows(env):
    c, raw = env
    with raw() as con:
        con.execute("UPDATE setting_version SET content_ref=? WHERE setting_version_id=1",
                    ('JUR-01 보도 파손: 수정구: 건설과 →    (근거 별표 1)',))
    r = submit(c, 1)
    assert (r.status_code, r.json()['error']['code']) == (422, 'content_format')
    with raw() as con:
        assert con.execute('SELECT dept_name FROM jurisdiction_dept').fetchone()[0] == '건설과'
