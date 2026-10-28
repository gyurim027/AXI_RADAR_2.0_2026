"""AI-03 위치 미확인 현황 API 시험 — 실제 DB 없이 돈다 (가짜 저장소). 시험에 실제 시설 값은 넣지 않는다."""
import pymysql
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ai03_location_api import _rate, router
from app.core import db
from app.core.auth import make_token
from app.core.responses import CamelCaseMiddleware, install_error_handlers
from app.services.ai03 import unlocated as un

COVERAGE = [{"table": "src_parking_enforce_place", "label": "단속장소", "total_rows": 23503, "missing_rows": 14483},
            {"table": "src_signal_controller", "label": "신호기", "total_rows": 1066, "missing_rows": 177},
            {"table": "src_police_signal", "label": "경찰 신호", "total_rows": 0, "missing_rows": 0},
            {"table": "src_complaint", "label": "민원", "total_rows": 281153, "missing_rows": 16494}]
ITEMS = [{"row_id": 11, "enforce_place": "시험용 장소 A", "enforce_cnt": 1520},
         {"row_id": 12, "enforce_place": "시험용 장소 B", "enforce_cnt": None}]


class FakeRepo(un.UnlocatedRepository):
    def __init__(self):
        self.calls = []

    def coverage(self):
        return [dict(c) for c in COVERAGE]

    def top_missing(self, limit):
        self.calls.append(limit)
        return ITEMS


@pytest.fixture()
def env():
    repo, old = FakeRepo(), un.get_repository()
    un.set_repository(repo)
    app = FastAPI()
    app.add_middleware(CamelCaseMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    yield TestClient(app), repo
    un.set_repository(old)


def _head(role, gu=None, uid=1):
    token, _ = make_token({"user_id": uid, "login_id": f"u{uid}", "role": role, "gu": gu, "org": None, "name": "시험"})
    return {"Authorization": f"Bearer {token}"}


def test_login_required(env):
    client, repo = env
    r = client.get("/api/ai03/unlocated")
    assert r.status_code == 401 and r.json()["error"]["code"] == "login_required"
    assert repo.calls == []                                           # 로그인 없이는 읽지 않는다


@pytest.mark.parametrize("role,gu", [("district", "분당구"), ("city", None)])
def test_only_operator_can_see(env, role, gu):
    client, repo = env
    r = client.get("/api/ai03/unlocated", headers=_head(role, gu))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_role"
    assert repo.calls == []


def test_operator_gets_coverage_and_top_in_camel_case(env):
    client, repo = env
    r = client.get("/api/ai03/unlocated", headers=_head("operator"))
    assert r.status_code == 200 and repo.calls == [20]                # 기본은 상위 20곳
    body = r.json()
    cov = body["coverage"]
    assert [c["label"] for c in cov] == ["단속장소", "신호기", "경찰 신호", "민원"]
    assert cov[0] == {"table": "src_parking_enforce_place", "label": "단속장소", "totalRows": 23503,
                      "missingRows": 14483, "missingRate": 61.6}
    assert cov[1]["missingRate"] == 16.6 and cov[3]["missingRate"] == 5.9
    assert cov[2]["missingRate"] == 0.0                               # 전체가 0이어도 0으로 나누지 않는다
    top = body["top"]
    assert top["table"] == "src_parking_enforce_place" and top["limit"] == 20 and top["totalMissing"] == 14483
    assert top["items"][0] == {"rowKey": "row_id=11", "name": "시험용 장소 A", "enforceCnt": 1520}
    assert top["items"][1]["enforceCnt"] is None


def test_limit_is_passed_and_validated(env):
    client, repo = env
    assert client.get("/api/ai03/unlocated?limit=5", headers=_head("operator")).json()["top"]["limit"] == 5
    assert repo.calls == [5]
    for bad in ("0", "101"):
        r = client.get(f"/api/ai03/unlocated?limit={bad}", headers=_head("operator"))
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    assert repo.calls == [5]                                          # 잘못된 값이면 읽지 않는다


def test_no_coordinates_in_response(env):
    client, _ = env
    text = client.get("/api/ai03/unlocated", headers=_head("operator")).text
    assert '"lat"' not in text and '"lon"' not in text               # 좌표 값은 내보내지 않는다


@pytest.mark.parametrize("missing,total,rate", [(14483, 23503, 61.6), (0, 0, 0.0), (1, 3, 33.3), (3, 3, 100.0)])
def test_rate(missing, total, rate):
    assert _rate(missing, total) == rate


# ── 12_오류 케이스: DB를 못 읽을 때 (ERR-11 · ERR-13) ─────────────────────────────
def test_db_read_failure_is_503_db_read_failed_without_leaking_details(env):
    client, repo = env

    def boom(*a):
        raise pymysql.err.OperationalError(2003, "Can't connect to MySQL server on '10.0.0.1'")
    repo.coverage = boom
    r = client.get("/api/ai03/unlocated", headers=_head("operator"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "db_read_failed"
    assert "10.0.0.1" not in r.text and "MySQL" not in r.text        # 서버 주소·오류 원문은 내보내지 않는다


def test_missing_db_settings_is_503_db_not_configured(env):
    client, repo = env

    def boom(*a):
        raise db.DbNotConfigured("DB 접속 정보가 없습니다.")
    repo.top_missing = boom
    r = client.get("/api/ai03/unlocated", headers=_head("operator"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "db_not_configured"


# ── 저장소가 보내는 SQL ────────────────────────────────────────────────────────
def test_repository_sql(monkeypatch):
    seen = []

    def fake(sql, args=None):
        seen.append((sql, args))
        if "COUNT" in sql:
            return [{"total_rows": 3, "missing_rows": None}]          # 빈 표나 좌표 없는 행이 없으면 SUM이 NULL
        return [{"row_id": 1, "enforce_place": "시험용", "enforce_cnt": 2}]
    monkeypatch.setattr(un.db, "read_only", fake)
    repo = un.UnlocatedRepository()
    cov = repo.coverage()
    assert [c["table"] for c in cov] == [t for t, _ in un.TABLES]
    assert cov[0]["total_rows"] == 3 and cov[0]["missing_rows"] == 0   # NULL은 0으로
    repo.top_missing(20)
    sql, args = seen[-1]
    assert "ORDER BY enforce_cnt DESC" in sql and "LIMIT %s" in sql and args == [20]   # 값은 자리표시자로
    assert all("lat IS NULL OR lon IS NULL" in q for q, _ in seen)    # 좌표 없음 기준이 모든 쿼리에서 같다
    assert all(a is None or a == [20] for _, a in seen)
