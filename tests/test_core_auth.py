"""로그인·권한(I-01)과 접근 기록(I-04) 시험. 실제 DB 없이 돈다.
실행: uv run python -m pytest tests/test_core_auth.py
"""
import unittest
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient

from app.core import access_audit as audit
from app.core.auth import (FailState, UserStore, allowed_gus, authenticate, current_user, decode_token,
                           get_user_store, hash_password, make_token, require_roles, verify_password)
from app.core.responses import ApiError
from app.main import app

PW = "test-pass-123"


class MemoryUserStore(UserStore):
    def __init__(self):
        h = hash_password(PW)
        self.users = {
            "suj": dict(user_id=1, login_id="suj", password_hash=h, display_name="수정", org_name="수정구청",
                        team_name="도로관리팀", gu_name="수정구", role="구 도로관리팀", is_active="Y"),
            "city": dict(user_id=2, login_id="city", password_hash=h, display_name="시", org_name="성남시",
                         team_name="도로과", gu_name=None, role="시 도로과", is_active="Y"),
            "stop": dict(user_id=3, login_id="stop", password_hash=h, display_name="중지", org_name=None,
                         team_name=None, gu_name=None, role="RADAR 운영자", is_active="N"),
        }
        self.fails = {}

    def get_by_login(self, login_id):
        return self.users.get(login_id)

    def fail_state(self, login_id, user):
        return self.fails.get(login_id, FailState())

    def save_fail_state(self, login_id, user, state):
        self.fails[login_id] = state


class MemoryAuditStore(audit.AuditStore):
    def __init__(self):
        self.rows = []

    def insert(self, actor_ref, kind, key, ip, reason):
        self.rows.append(dict(actor_ref=actor_ref, kind=kind, key=key, ip=ip, reason=reason,
                              at=int(datetime.now().timestamp())))

    def exists_since(self, actor_ref, kind, key, reason, since_epoch):
        return any(r["actor_ref"] == actor_ref and r["kind"] == kind and r["key"] == key and r["reason"] == reason
                   and r["at"] >= since_epoch for r in self.rows)


# 시험용 기능 API (실제 기능이 붙는 모양)
demo = APIRouter(prefix="/api/demo-auth")


@demo.get("/points")
def points(gu: str, request: Request, user: dict = Depends(current_user)):
    return {"new_row": audit.complaint_points(request, user, gu, reason="점검 후보 검토"), "gus": allowed_gus(user)}


@demo.get("/city-only", dependencies=[Depends(require_roles("city"))])
def city_only():
    return {"ok": True}


app.include_router(demo)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryUserStore()
        self.audit = MemoryAuditStore()
        app.dependency_overrides[get_user_store] = lambda: self.store
        audit.set_store(self.audit)
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")

    def tearDown(self):
        app.dependency_overrides.clear()
        audit.set_store(audit.AuditStore())

    def login(self, login_id="suj", pw=PW):
        return self.c.post("/api/auth/login", json={"loginId": login_id, "password": pw})

    def bearer(self, login_id="suj"):
        return {"Authorization": "Bearer " + self.login(login_id).json()["token"]}

    # ── 비밀번호·토큰
    def test_hash_is_not_plain(self):
        h = hash_password(PW)
        self.assertNotIn(PW, h)
        self.assertTrue(verify_password(PW, h))
        self.assertFalse(verify_password("wrong", h))
        self.assertFalse(verify_password(PW, "plain-text"))

    def test_token_tamper_and_expiry(self):
        tok, _ = make_token({"user_id": 1, "login_id": "suj", "role": "district", "gu": "수정구"})
        self.assertEqual(decode_token(tok)["login"], "suj")
        head, body, sig = tok.split(".")
        with self.assertRaises(ApiError):
            decode_token(f"{head}.{body}.x{sig[1:]}")
        with self.assertRaises(ApiError) as e:
            decode_token(tok, now=10 ** 11)
        self.assertEqual(e.exception.code, "token_expired")

    # ── 로그인 API
    def test_login_ok_shape(self):
        r = self.login()
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["tokenType"], "Bearer")
        self.assertEqual(j["user"], {"id": "suj", "role": "district", "gu": "수정구", "org": "수정구청 도로관리팀",
                                     "name": "수정", "readOnly": False})
        self.assertNotIn("password", r.text.lower().replace("password\"", ""))
        self.assertEqual(self.audit.rows[-1]["kind"], "로그인")

    def test_wrong_then_lock_after_5(self):
        for left in (4, 3, 2, 1):
            r = self.login(pw="x")
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()["error"]["remaining"], left)
        r = self.login(pw="x")
        self.assertEqual(r.status_code, 423)
        self.assertEqual(r.json()["error"]["lockMinutes"], 10)
        self.assertEqual(self.login().status_code, 423)            # 맞는 비밀번호도 잠김 동안은 안 됨

    def test_lock_expires(self):
        self.store.fails["suj"] = FailState(0, datetime.now() - timedelta(seconds=1))
        self.assertEqual(self.login().status_code, 200)

    def test_unknown_id_same_answer(self):
        r = self.login("nobody")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], "wrong_password")

    def test_inactive(self):
        self.assertEqual(self.login("stop").json()["error"]["code"], "inactive_account")

    def test_success_resets_count(self):
        self.login(pw="x"); self.login(pw="x")
        self.login()
        self.assertEqual(self.login(pw="x").json()["error"]["remaining"], 4)

    def test_me(self):
        self.assertEqual(self.c.get("/api/auth/me").status_code, 401)
        r = self.c.get("/api/auth/me", headers=self.bearer())
        self.assertEqual(r.json()["user"]["id"], "suj")

    # ── 권한
    def test_role_guard(self):
        self.assertEqual(self.c.get("/api/demo-auth/city-only", headers=self.bearer("suj")).status_code, 403)
        self.assertEqual(self.c.get("/api/demo-auth/city-only", headers=self.bearer("city")).status_code, 200)

    def test_gu_scope(self):
        h = self.bearer("suj")
        self.assertEqual(self.c.get("/api/demo-auth/points?gu=중원구", headers=h).status_code, 403)
        r = self.c.get("/api/demo-auth/points?gu=수정구", headers=self.bearer("city"))
        self.assertEqual(r.json()["gus"], ["수정구", "중원구", "분당구"])

    # ── 접근 기록 (POL-022: 로그인 한 번 동안 구마다 한 줄)
    def test_points_once_per_login_per_gu(self):
        h = self.bearer("city")
        got = [self.c.get(f"/api/demo-auth/points?gu={g}", headers=h).json()["newRow"]
               for g in ("수정구", "수정구", "중원구", "수정구")]
        self.assertEqual(got, [True, False, True, False])
        rows = [r for r in self.audit.rows if r["kind"] == "민원 점 위치"]
        self.assertEqual([r["key"] for r in rows], ["수정구", "중원구"])
        self.assertEqual(rows[0]["reason"], "점검 후보 검토")
        self.assertTrue(rows[0]["ip"])

    def test_bad_kind_rejected(self):
        with self.assertRaises(ValueError):
            audit.record(None, {"user_id": 1}, "아무거나")

    def test_authenticate_direct(self):
        u = authenticate(self.store, "city", PW)
        self.assertEqual((u["role"], u["gu"]), ("city", None))


if __name__ == "__main__":
    unittest.main()
