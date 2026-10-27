"""AI-03 좌표 결과 조회 API 시험 — 실제 DB 없이 돈다 (가짜 저장소·가짜 접근 기록). 시험에 실제 민원 값은 넣지 않는다."""
import pymysql
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ai03_location_api import REASON, _kind, router
from app.core import access_audit as audit
from app.core import db
from app.core.auth import make_token
from app.core.responses import CamelCaseMiddleware, install_error_handlers
from app.services.ai03 import low_complaints as lc

ROWS = [{"complaint_id": "C-TEST-0001", "source_type": "일반 민원", "received_date": None,
         "location_text": "시험용 위치 글자 A", "gu": "분당구", "admin_dong_name": "시험동", "gid": "다사00aa00aa",
         "lat": 37.40, "lon": 127.10, "coord_method": "AI-03 규칙+브이월드 / 장소 검색", "coord_accuracy": "낮음"},
        {"complaint_id": "C-TEST-0002", "source_type": "일반 민원", "received_date": None,
         "location_text": "시험용 위치 글자 B", "gu": None, "admin_dong_name": None, "gid": "다사00aa00ab",
         "lat": 37.41, "lon": 127.11, "coord_method": "주소 변환(장소 이름 검색)", "coord_accuracy": "낮음"}]


class FakeRepo(lc.LowComplaintRepository):
    def __init__(self):
        self.calls = []

    def list_low(self, gus, include_no_gu, limit, offset):
        self.calls.append((gus, include_no_gu, limit, offset))
        return ROWS, len(ROWS)


class MemAudit(audit.AuditStore):
    def __init__(self):
        self.rows = []

    def insert(self, actor_ref, kind, key, ip, reason):
        self.rows.append((actor_ref, kind, key, reason))

    def exists_since(self, actor_ref, kind, key, reason, since_epoch):
        return (actor_ref, kind, key, reason) in self.rows


@pytest.fixture()
def env():
    repo, mem, old_audit, old_repo = FakeRepo(), MemAudit(), audit.get_store(), lc.get_repository()
    lc.set_repository(repo)
    audit.set_store(mem)
    app = FastAPI()
    app.add_middleware(CamelCaseMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    yield TestClient(app), repo, mem
    lc.set_repository(old_repo)
    audit.set_store(old_audit)


def _head(role, gu=None, uid=1):
    token, _ = make_token({"user_id": uid, "login_id": f"u{uid}", "role": role, "gu": gu, "org": None, "name": "시험"})
    return {"Authorization": f"Bearer {token}"}


def test_login_required(env):
    client, repo, mem = env
    r = client.get("/api/ai03/low-complaints")
    assert r.status_code == 401 and r.json()["error"]["code"] == "login_required"
    assert repo.calls == [] and mem.rows == []                      # 로그인 없이는 읽지도, 기록하지도 않는다


def test_district_sees_only_own_gu(env):
    client, repo, mem = env
    r = client.get("/api/ai03/low-complaints", headers=_head("district", "분당구"))
    assert r.status_code == 200
    assert repo.calls == [(["분당구"], False, 200, 0)]               # 자기 구만, 구 없는 격자는 제외
    assert mem.rows == [(1, audit.COMPLAINT_POINTS, "분당구", REASON)]


def test_district_other_gu_forbidden(env):
    client, repo, mem = env
    r = client.get("/api/ai03/low-complaints?gu=수정구", headers=_head("district", "분당구"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_gu"
    assert repo.calls == [] and mem.rows == []


@pytest.mark.parametrize("role", ["city", "operator"])
def test_city_and_operator_see_all_with_audit_per_gu(env, role):
    client, repo, mem = env
    r = client.get("/api/ai03/low-complaints", headers=_head(role))
    assert r.status_code == 200
    assert repo.calls == [(None, True, 200, 0)]                      # 구 제한 없음, 구 없는 격자 포함
    assert [x[2] for x in mem.rows] == ["수정구", "중원구", "분당구"]   # 구마다 접근 기록 한 줄


def test_audit_once_per_login_same_gu_and_reason(env):
    client, _, mem = env
    h = _head("district", "분당구")
    client.get("/api/ai03/low-complaints", headers=h)
    client.get("/api/ai03/low-complaints", headers=h)
    assert len(mem.rows) == 1                                        # 같은 구·같은 목적이면 한 줄만


def test_response_is_camel_case_and_has_method_kind(env):
    client, _, _ = env
    body = client.get("/api/ai03/low-complaints", headers=_head("operator")).json()
    assert body["total"] == 2 and body["limit"] == 200 and body["offset"] == 0
    first = body["complaints"][0]
    assert first["complaintId"] == "C-TEST-0001" and first["coordAccuracy"] == "낮음"
    assert first["locationText"] and first["adminDongName"] == "시험동"
    assert [c["methodKind"] for c in body["complaints"]] == ["장소", "장소"]
    assert body["complaints"][1]["gu"] is None                       # 구 없는 격자의 민원은 gu가 null


def test_limit_validation(env):
    client, repo, _ = env
    r = client.get("/api/ai03/low-complaints?limit=0", headers=_head("operator"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    assert repo.calls == []


@pytest.mark.parametrize("method,kind", [
    ("주소 변환(장소 이름 검색)", "장소"),                              # v2.1 79에 있는 값
    ("원본 좌표(본문 위치값)", "본문 위치값"),
    ("주소 변환(지번 주소)", "주소"),
    ("AI-03 규칙+브이월드 / 5차 — 장소 검색 — 검색어 'x'", "장소"),      # AI-03 반영 뒤 들어올 값
    ("AI-03 규칙+내부대조 / 5차 — 내부 대조(버스정류장명)", "내부 대조"),
    (None, None),
])
def test_method_kind(method, kind):
    assert _kind(method) == kind


# ── 12_오류 케이스: DB를 못 읽을 때 (ERR-11 · ERR-13) ─────────────────────────────
def test_db_read_failure_is_503_db_read_failed_without_leaking_details(env):
    client, repo, mem = env

    def boom(*a):
        raise pymysql.err.OperationalError(2003, "Can't connect to MySQL server on '10.0.0.1'")
    repo.list_low = boom
    r = client.get("/api/ai03/low-complaints", headers=_head("operator"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "db_read_failed"
    assert "10.0.0.1" not in r.text and "MySQL" not in r.text            # 서버 주소·오류 원문은 내보내지 않는다


def test_missing_db_settings_is_503_db_not_configured(env):
    client, repo, _ = env

    def boom(*a):
        raise db.DbNotConfigured("DB 접속 정보가 없습니다.")
    repo.list_low = boom
    r = client.get("/api/ai03/low-complaints", headers=_head("city"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "db_not_configured"


def test_if_the_access_record_cannot_be_written_nothing_is_shown(env):
    client, repo, mem = env

    def boom(*a):
        raise pymysql.err.OperationalError(2013, "Lost connection")
    mem.insert = boom
    r = client.get("/api/ai03/low-complaints", headers=_head("district", "분당구"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "db_read_failed"
    assert repo.calls == []                                               # 접근 기록 없이는 민원 점 위치를 안 보여 준다
