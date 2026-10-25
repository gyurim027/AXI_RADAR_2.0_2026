"""계정 관리(I-01)·접속 기록 조회(I-04) API 시험. 실제 DB 없이 돈다.
실행: uv run python -m pytest tests/test_accounts_api.py
"""
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core import access_audit
from app.core.auth import make_token, verify_password
from app.main import app
from app.services.accounts import repository as ar


class MemoryAudit(access_audit.AuditStore):
    def __init__(self):
        self.rows = []

    def insert(self, actor_ref, kind, key, ip, reason):
        self.rows.append(dict(actor_ref=actor_ref, kind=kind, key=key, ip=ip, reason=reason))


class MemoryRepo(ar.AccountRepository):
    def __init__(self):
        self.users = {
            1: dict(user_id=1, login_id="operator", display_name="운영자", org_name="RADAR", team_name="RADAR 운영팀",
                    gu_name=None, role="RADAR 운영자", is_active="Y", created_at=datetime(2026, 10, 1), password_hash="x"),
            2: dict(user_id=2, login_id="suj", display_name="김수정", org_name="수정구청", team_name="건설과 도로관리팀",
                    gu_name="수정구", role="구 도로관리팀", is_active="Y", created_at=datetime(2026, 10, 1), password_hash="x"),
        }
        self.log, self.access = [], [
            dict(access_audit_id=1, accessed_at=datetime.now() - timedelta(days=1), resource_kind="로그인",
                 resource_key=None, client_ip="10.0.0.2", access_reason="로그인", login_id="suj",
                 display_name="김수정", org_name="수정구청", team_name="건설과 도로관리팀"),
            dict(access_audit_id=2, accessed_at=datetime.now() - timedelta(days=40), resource_kind="파일 내려받기",
                 resource_key="보고서", client_ip="10.0.0.1", access_reason=None, login_id="operator",
                 display_name="운영자", org_name="RADAR", team_name="RADAR 운영팀"),
        ]

    def list_accounts(self):
        return [dict(u, last_login_at=datetime(2026, 10, 25) if u["login_id"] == "suj" else None)
                for u in self.users.values()]

    def get_account(self, login_id):
        return next((dict(u) for u in self.users.values() if u["login_id"] == login_id), None)

    def create_account(self, row, password_hash, by, reason):
        uid = max(self.users) + 1
        self.users[uid] = dict(user_id=uid, login_id=row["login_id"], display_name=row["name"], org_name=row["org"],
                               team_name=row["team"], gu_name=row["gu"], role=row["role"], is_active="Y",
                               created_at=datetime.now(), password_hash=password_hash)
        self._add_log(uid, by, None, row["role"], None, row["gu"], reason)
        return uid

    def set_active(self, user, active, by, reason):
        self.users[user["user_id"]]["is_active"] = "Y" if active else "N"
        if active:
            self._add_log(user["user_id"], by, None, user["role"], None, user["gu_name"], reason)
        else:
            self._add_log(user["user_id"], by, user["role"], None, user["gu_name"], None, reason)

    def change_role(self, user, role, gu, by, reason):
        self.users[user["user_id"]].update(role=role, gu_name=gu)
        self._add_log(user["user_id"], by, user["role"], role, user["gu_name"], gu, reason)

    def set_password(self, user_id, password_hash):
        self.users[user_id]["password_hash"] = password_hash

    def _add_log(self, target, by, old_role, new_role, old_gu, new_gu, reason):
        self.log.append(dict(role_change_id=len(self.log) + 1, changed_at=datetime.now(), target_login=self.users[target]["login_id"],
                             target_name=self.users[target]["display_name"], old_role=old_role, new_role=new_role,
                             old_gu_name=old_gu, new_gu_name=new_gu, by_name=self.users[by]["display_name"], reason=reason))

    def role_log(self, limit):
        return list(reversed(self.log))[:limit]

    def list_access(self, days, login_id, kind, limit, now=None):
        since = datetime.now() - timedelta(days=days)
        return [r for r in self.access if r["accessed_at"] >= since and (not login_id or r["login_id"] == login_id)
                and (not kind or r["resource_kind"] == kind)][:limit]


def _h(role="operator", uid=1, gu=None):
    tok, _ = make_token({"user_id": uid, "login_id": role, "role": role, "gu": gu})
    return {"Authorization": f"Bearer {tok}"}


class AccountsApiTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.audit = MemoryRepo(), MemoryAudit()
        ar.set_repository(self.repo)
        access_audit.set_store(self.audit)
        self.c = TestClient(app)

    def tearDown(self):
        ar.set_repository(ar.AccountRepository())
        access_audit.set_store(access_audit.AuditStore())

    def test_operator_only(self):
        self.assertEqual(self.c.get("/api/admin/accounts").status_code, 401)
        self.assertEqual(self.c.get("/api/admin/accounts", headers=_h("city", 5)).status_code, 403)

    def test_list_matches_mock_shape(self):
        j = self.c.get("/api/admin/accounts", headers=_h()).json()
        suj = next(r for r in j["rows"] if r["id"] == "suj")
        self.assertEqual((suj["role"], suj["gu"], suj["status"], suj["last"]), ("구 도로관리팀", "수정구", "사용 중", "2026.10.25"))
        self.assertEqual(j["roles"], ["시 도로과", "구 도로관리팀", "RADAR 운영자"])

    def test_create(self):
        r = self.c.post("/api/admin/accounts", headers=_h(),
                        json={"role": "구 도로관리팀", "gu": "분당구", "name": "새 담당", "loginId": "bd2"})
        j = r.json()
        self.assertEqual(r.status_code, 200)
        temp = j["tempPassword"]
        u = self.repo.get_account("bd2")
        self.assertTrue(verify_password(temp, u["password_hash"]))       # 해시만 저장
        self.assertNotIn(temp, str(self.audit.rows))                     # 기록에 비밀번호 없음
        self.assertEqual((u["org_name"], u["team_name"]), ("분당구 건설과", "도로관리팀"))
        self.assertEqual(self.repo.log[-1]["new_role"], "구 도로관리팀")  # 61 권한 기록
        self.assertEqual(self.audit.rows[-1]["kind"], "설정 변경")

    def test_create_errors(self):
        h = _h()
        self.assertEqual(self.c.post("/api/admin/accounts", headers=h, json={"role": "구 도로관리팀", "name": "a", "loginId": "a"})
                         .json()["error"]["code"], "gu_required")
        self.assertEqual(self.c.post("/api/admin/accounts", headers=h, json={"role": "시 도로과", "name": "", "loginId": "a"})
                         .json()["error"]["code"], "required")
        self.assertEqual(self.c.post("/api/admin/accounts", headers=h, json={"role": "시 도로과", "name": "a", "loginId": "suj"})
                         .status_code, 409)
        self.assertEqual(self.c.post("/api/admin/accounts", headers=h, json={"role": "관리자", "name": "a", "loginId": "b"})
                         .json()["error"]["code"], "invalid_role")

    def test_status_and_self(self):
        h = _h()
        self.assertEqual(self.c.patch("/api/admin/accounts/operator/status", headers=h, json={"status": "멈춤"}).status_code, 403)
        r = self.c.patch("/api/admin/accounts/suj/status", headers=h, json={"status": "멈춤"}).json()
        self.assertTrue(r["changed"])
        self.assertEqual(self.repo.users[2]["is_active"], "N")
        self.assertEqual((self.repo.log[-1]["old_role"], self.repo.log[-1]["new_role"]), ("구 도로관리팀", None))   # 거둠
        self.assertFalse(self.c.patch("/api/admin/accounts/suj/status", headers=h, json={"status": "멈춤"}).json()["changed"])
        self.assertEqual(self.c.patch("/api/admin/accounts/없음/status", headers=h, json={"status": "멈춤"}).status_code, 404)

    def test_role_change(self):
        h = _h()
        r = self.c.patch("/api/admin/accounts/suj/role", headers=h, json={"role": "구 도로관리팀", "gu": "중원구", "reason": "인사 이동"})
        self.assertTrue(r.json()["changed"])
        last = self.repo.log[-1]
        self.assertEqual((last["old_gu_name"], last["new_gu_name"], last["reason"]), ("수정구", "중원구", "인사 이동"))
        self.assertEqual(self.c.patch("/api/admin/accounts/suj/role", headers=h, json={"role": "시 도로과"}).status_code, 422)  # 이유 필수

    def test_password_reset(self):
        j = self.c.post("/api/admin/accounts/suj/password-reset", headers=_h()).json()
        self.assertTrue(verify_password(j["tempPassword"], self.repo.users[2]["password_hash"]))

    def test_access_list(self):
        j = self.c.get("/api/admin/access", headers=_h()).json()
        self.assertEqual([r["accountId"] for r in j["rows"]], ["suj"])                 # 30일 안만
        self.assertEqual(j["rows"][0]["who"], "김수정 (수정구청 건설과 도로관리팀)")
        self.assertIn("로그인", j["actions"])
        j = self.c.get("/api/admin/access?days=60&action=파일 내려받기", headers=_h()).json()
        self.assertEqual([r["accountId"] for r in j["rows"]], ["operator"])
        self.assertEqual(self.c.get("/api/admin/access?action=아무거나", headers=_h()).status_code, 400)


class StillValidTests(unittest.TestCase):
    """멈춘 계정·바뀐 역할은 토큰이 살아 있어도 막는다 (DB가 있을 때)."""

    def setUp(self):
        from unittest import mock
        from app.core import auth, db
        self.auth = auth
        self.p1 = mock.patch.object(db, "is_configured", return_value=True)
        self.p1.start()
        self.state = {"role": "구 도로관리팀", "gu_name": "수정구", "is_active": "Y"}
        self.p2 = mock.patch.object(auth, "_account_state", side_effect=lambda uid: self.state)
        self.p2.start()
        self.c = TestClient(app)

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()

    def test_blocks(self):
        h = _h("district", 2, "수정구")
        self.assertEqual(self.c.get("/api/auth/me", headers=h).status_code, 200)
        self.state["is_active"] = "N"
        self.assertEqual(self.c.get("/api/auth/me", headers=h).json()["error"]["code"], "account_inactive")
        self.state.update(is_active="Y", gu_name="중원구")
        self.assertEqual(self.c.get("/api/auth/me", headers=h).json()["error"]["code"], "role_changed")


if __name__ == "__main__":
    unittest.main()
