"""I-02 실제 조회 SQL·HTTP 권한·I-07 처리 후 동일 ID 재조회. 격리 SQLite 방언 시험."""
import pytest
from test_approvals_api import env, headers


def test_read_only_rows_and_identity(env):
    c, raw = env
    with raw() as con:
        before = list(con.execute('SELECT * FROM setting_version ORDER BY setting_version_id'))
    r = c.get('/api/settings/versions?limit=2', headers=headers('operator', 7))
    assert r.status_code == 200
    body = r.json()
    assert [v['settingVersionId'] for v in body['versions']] == [6, 5]
    assert body['hasMore'] is True
    assert [v['settingVersionId'] for v in c.get('/api/settings/versions?limit=2&offset=2', headers=headers('operator', 7)).json()['versions']] == [3, 2]
    for sid in (3, 5):
        item = c.get(f'/api/settings/versions/{sid}', headers=headers('operator', 7)).json()
        assert item['settingVersionId'] == sid
        assert item['versionLabel'] == 'v1'  # 같은 이름이라도 ID가 다름
        assert item['contentRef'] is None
    with raw() as con:
        assert list(con.execute('SELECT * FROM setting_version ORDER BY setting_version_id')) == before


@pytest.mark.parametrize('role', ['city', 'district'])
def test_operator_only(env, role):
    c, _ = env
    assert c.get('/api/settings/versions', headers=headers(role)).status_code == 403
    assert c.get('/api/settings/versions/2', headers=headers(role)).status_code == 403


def test_anonymous_and_write_not_supported(env):
    c, _ = env
    assert c.get('/api/settings/versions').status_code == 401
    assert c.post('/api/settings/versions', headers=headers('operator', 7), json={}).status_code == 405


@pytest.mark.parametrize('query', ['status=작성 중', 'kind=담당 부서 표', 'limit=0', 'offset=-1'])
def test_invalid_filter(env, query):
    c, _ = env
    assert c.get('/api/settings/versions?' + query, headers=headers('operator', 7)).status_code == 422


def test_filters_not_found_and_original_text(env):
    c, raw = env
    r = c.get('/api/settings/versions?status=승인', headers=headers('operator', 7)).json()
    assert [v['settingVersionId'] for v in r['versions']] == [3]
    assert r['hasMore'] is False
    assert c.get('/api/settings/versions?kind=가중치&status=승인', headers=headers('operator', 7)).json()['versions'] == []
    for sid in (1, 4, 999):
        assert c.get(f'/api/settings/versions/{sid}', headers=headers('operator', 7)).status_code == 404
    content = '<script>notExecuted()</script> 파일 위치 또는 원문'
    with raw() as con:
        con.execute('UPDATE setting_version SET content_ref=? WHERE setting_version_id=2', (content,))
    assert c.get('/api/settings/versions/2', headers=headers('operator', 7)).json()['contentRef'] == content


@pytest.mark.parametrize('decision', ['승인', '돌려보냄'])
def test_operator_reads_city_review_same_id(env, decision):
    c, _ = env
    assert c.post('/api/approvals/2/review', headers=headers('operator', 7), json={'decision': '승인'}).status_code == 403
    r = c.post('/api/approvals/2/review', headers=headers('city', 22), json={'decision': decision, 'reviewComment': '설정 검토 결과'})
    assert r.status_code == 200
    assert r.json()['departmentApplied'] is False
    assert r.json()['recalculationStarted'] is False
    item = c.get('/api/settings/versions/2', headers=headers('operator', 7)).json()
    assert item['settingVersionId'] == 2
    assert item['approvalStatus'] == decision
    assert item['approvedBy'] == 22
    assert item['approvedAt'] is not None
    assert item['reviewComment'] == '설정 검토 결과'


def test_query_error_is_not_empty_success(env, monkeypatch):
    from app.core import db
    c, _ = env
    def fail(*args):
        raise RuntimeError('isolated query failure')
    monkeypatch.setattr(db, 'read_only', fail)
    r = c.get('/api/settings/versions', headers=headers('operator', 7))
    assert r.status_code == 500
    assert 'versions' not in r.json()
