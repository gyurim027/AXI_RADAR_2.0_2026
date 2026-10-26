"""계정 관리(I-01)·접속 기록 조회(I-04) DB 읽기·쓰기. 표: 60 app_user · 61 role_change_log · 70 access_audit (SQL v2.1~).

- 60·61의 번호(user_id, role_change_id)는 자동 번호가 아니라서 한 거래 안에서 MAX + 1로 정한다.
- 61에는 역할을 주고(old 비움)·바꾸고·거둘(new 비움) 때마다 한 줄. 3년 이상 보관(POL-022, 고시 제5조③).
- 70은 읽기만 한다. 고치거나 지우는 함수는 만들지 않는다 (고시 제8조).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.core import db

ACCOUNT_COLS = ("user_id, login_id, display_name, org_name, team_name, gu_name, role, is_active, created_at")


class AccountRepository:
    # ── 60 계정 ─────────────────────────────────────
    def list_accounts(self) -> list[dict]:
        return db.read_only(
            f"SELECT {', '.join('u.' + c.strip() for c in ACCOUNT_COLS.split(','))}, "
            "(SELECT MAX(a.accessed_at) FROM access_audit a WHERE a.actor_ref = u.user_id "
            "AND a.resource_kind = '로그인') AS last_login_at "
            "FROM app_user u ORDER BY u.user_id")

    def get_account(self, login_id: str) -> dict | None:
        rows = db.read_only(f"SELECT {ACCOUNT_COLS} FROM app_user WHERE login_id = %s", (login_id,))
        return rows[0] if rows else None

    def create_account(self, row: dict, password_hash: str, by: int, reason: str) -> int:
        """60에 한 줄 + 61에 '역할을 줌' 한 줄을 한 거래로. 아이디가 겹치면 None 대신 ValueError('duplicate')."""
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("SELECT 1 FROM app_user WHERE login_id = %s FOR UPDATE", (row["login_id"],))
                if cur.fetchone():
                    raise ValueError("duplicate")
                cur.execute("SELECT COALESCE(MAX(user_id), 0) + 1 AS n FROM app_user FOR UPDATE")
                user_id = int(cur.fetchone()["n"])
                cur.execute(
                    "INSERT INTO app_user (user_id, login_id, password_hash, display_name, org_name, team_name, "
                    "gu_name, role, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Y', NOW())",
                    (user_id, row["login_id"], password_hash, row["name"], row["org"], row["team"], row["gu"],
                     row["role"]))
                self._log(cur, user_id, by, None, row["role"], None, row["gu"], reason)
            con.commit()
        return user_id

    def set_active(self, user: dict, active: bool, by: int, reason: str) -> None:
        """멈춤 = 역할을 거둠(61 new 비움), 다시 쓰기 = 역할을 다시 줌(61 old 비움)."""
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("UPDATE app_user SET is_active = %s WHERE user_id = %s",
                            ("Y" if active else "N", user["user_id"]))
                if active:
                    self._log(cur, user["user_id"], by, None, user["role"], None, user["gu_name"], reason)
                else:
                    self._log(cur, user["user_id"], by, user["role"], None, user["gu_name"], None, reason)
            con.commit()

    def change_role(self, user: dict, role: str, gu: str | None, by: int, reason: str) -> None:
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("UPDATE app_user SET role = %s, gu_name = %s WHERE user_id = %s",
                            (role, gu, user["user_id"]))
                self._log(cur, user["user_id"], by, user["role"], role, user["gu_name"], gu, reason)
            con.commit()

    def set_password(self, user_id: int, password_hash: str) -> None:
        """비밀번호를 바꾸면 잠금도 푼다 (failed_count 0, locked_until 비움)."""
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("UPDATE app_user SET password_hash = %s, failed_count = 0, locked_until = NULL "
                            "WHERE user_id = %s", (password_hash, user_id))
            con.commit()

    @staticmethod
    def _log(cur, target: int, by: int, old_role, new_role, old_gu, new_gu, reason: str) -> None:
        cur.execute("SELECT COALESCE(MAX(role_change_id), 0) + 1 AS n FROM role_change_log FOR UPDATE")
        n = int(cur.fetchone()["n"])
        cur.execute(
            "INSERT INTO role_change_log (role_change_id, target_user_id, changed_by, old_role, new_role, "
            "old_gu_name, new_gu_name, changed_at, reason) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)",
            (n, target, by, old_role, new_role, old_gu, new_gu, (reason or "")[:255] or None))

    # ── 61 권한 변경 기록 ───────────────────────────
    def role_log(self, limit: int) -> list[dict]:
        return db.read_only(
            "SELECT r.role_change_id, r.changed_at, t.display_name AS target_name, t.login_id AS target_login, "
            "r.old_role, r.new_role, r.old_gu_name, r.new_gu_name, b.display_name AS by_name, r.reason "
            "FROM role_change_log r LEFT JOIN app_user t ON t.user_id = r.target_user_id "
            "LEFT JOIN app_user b ON b.user_id = r.changed_by "
            "ORDER BY r.changed_at DESC, r.role_change_id DESC LIMIT %s", (limit,))

    # ── 70 접속 기록 (읽기만) ───────────────────────
    def list_access(self, days: int, login_id: str | None, kind: str | None, limit: int,
                    now: datetime | None = None) -> list[dict]:
        since = (now or datetime.now()) - timedelta(days=days)
        sql = ("SELECT a.access_audit_id, a.accessed_at, a.resource_kind, a.resource_key, a.client_ip, a.access_reason, "
               "u.login_id, u.display_name, u.org_name, u.team_name "
               "FROM access_audit a LEFT JOIN app_user u ON u.user_id = a.actor_ref WHERE a.accessed_at >= %s")
        args: list = [since]
        if login_id:
            sql += " AND u.login_id = %s"
            args.append(login_id)
        if kind:
            sql += " AND a.resource_kind = %s"
            args.append(kind)
        sql += " ORDER BY a.accessed_at DESC, a.access_audit_id DESC LIMIT %s"
        args.append(limit)
        return db.read_only(sql, args)


_repo: AccountRepository = AccountRepository()


def set_repository(repo: AccountRepository) -> None:
    global _repo
    _repo = repo


def get_repository() -> AccountRepository:
    return _repo
