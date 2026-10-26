"""로그인·권한 (I-01, W05-03 골격 7번, 초안 v0.1).

하는 일
- 아이디·비밀번호 확인 → 토큰(JWT, HS256) 발급. 화면은 요청 머리 `Authorization: Bearer <토큰>`으로 보낸다.
- 5번 틀리면 10분 잠금 (POL-022, 화면 CM-01 2). 없는 아이디도 똑같이 세어, 아이디가 있는지 알려 주지 않는다.
- 역할 3개: DB 60 app_user.role(한글) ↔ 화면 코드
      구 도로관리팀 = district (자기 구만) · 시 도로과 = city · RADAR 운영자 = operator
- 기능 API에 붙이는 법
      from fastapi import Depends
      from app.core.auth import current_user, require_roles, allowed_gus

      @router.get("/candidates")
      def candidates(user: dict = Depends(current_user)):          # 로그인만 확인
          gus = allowed_gus(user)                                   # district면 [자기 구], 나머지는 3개 구 전체
          ...

      @router.post("/approve", dependencies=[Depends(require_roles("city"))])   # 시 도로과만
      def approve(...): ...

저장 규칙
- 비밀번호는 해시만 저장(scrypt, 파이썬 표준 라이브러리). 원문은 저장·로그 X.
- 틀린 횟수·잠긴 시각은 60 app_user의 failed_count·locked_until 칸에 둔다(SQL v2.1에서 추가).
  칸이 아직 없는 DB에서는 서버 메모리에 둔다(서버를 다시 켜면 초기화) — v2.1 전까지 임시.
- 토큰 서명 키는 .env의 RADAR_JWT_SECRET. 비어 있으면 dev에서만 서버를 켤 때마다 임시 키를 만든다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.responses import ApiError

logger = logging.getLogger("radar.auth")

MAX_FAILS = 5
LOCK_MINUTES = 10
GU_LIST = ("수정구", "중원구", "분당구")
ROLE_CODES = {"구 도로관리팀": "district", "시 도로과": "city", "RADAR 운영자": "operator"}
ROLE_NAMES = {v: k for k, v in ROLE_CODES.items()}
INACTIVE = {"n", "no", "0", "false", "아니오", "사용 안 함", "중지"}


# ── 비밀번호 해시 ─────────────────────────────────────

_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    """'scrypt$n$r$p$소금$해시' 한 줄 (60 app_user.password_hash에 넣는 값)."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algo, n, r, p, salt, dk = (stored or "").split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(_unb64(dk)))
        return hmac.compare_digest(got, _unb64(dk))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_hex(8))    # 없는 아이디도 같은 시간이 걸리게


# ── 토큰 (JWT HS256) ─────────────────────────────────

@lru_cache(maxsize=1)
def _secret() -> bytes:
    s = get_settings()
    if s.auth.jwt_secret:
        return s.auth.jwt_secret.encode("utf-8")
    if s.app_env != "dev":
        raise RuntimeError("RADAR_JWT_SECRET이 없습니다 (.env). dev가 아닌 환경에서는 꼭 넣어야 합니다.")
    logger.warning("RADAR_JWT_SECRET이 없어 임시 키를 씁니다. 서버를 다시 켜면 다시 로그인해야 합니다.")
    return secrets.token_bytes(32)


def make_token(user: dict, now: float | None = None) -> tuple[str, int]:
    now = int(now or time.time())
    exp = now + int(get_settings().auth.token_hours * 3600)
    payload = {"sub": str(user["user_id"]), "login": user["login_id"], "role": user["role"],
               "gu": user.get("gu"), "org": user.get("org"), "name": user.get("name"), "iat": now, "exp": exp, "jti": secrets.token_hex(8)}
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    sig = _b64(hmac.new(_secret(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}", exp - now


def decode_token(token: str, now: float | None = None) -> dict:
    try:
        head, body, sig = token.split(".")
        want = _b64(hmac.new(_secret(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, want):
            raise ValueError
        if json.loads(_unb64(head)).get("alg") != "HS256":
            raise ValueError
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        raise ApiError(401, "invalid_token", "다시 로그인해 주세요") from None
    if int(payload.get("exp", 0)) <= int(now or time.time()):
        raise ApiError(401, "token_expired", "로그인 시간이 지났습니다. 다시 로그인해 주세요")
    return payload


# ── 계정 저장소 (DB 60 app_user) ─────────────────────

@dataclass
class FailState:
    count: int = 0
    locked_until: datetime | None = None


class UserStore:
    """60 app_user를 읽고, 틀린 횟수를 적는다. 시험에서는 MemoryUserStore로 바꿔 끼운다."""

    _mem: dict[str, FailState] = {}
    _lock = threading.Lock()

    def get_by_login(self, login_id: str) -> dict | None:
        from app.core import db
        rows = db.read_only(
            "SELECT user_id, login_id, password_hash, display_name, org_name, team_name, gu_name, role, is_active "
            "FROM app_user WHERE login_id = %s", (login_id,))
        return rows[0] if rows else None

    @staticmethod
    @lru_cache(maxsize=1)
    def has_lock_columns() -> bool:
        from app.core import db
        try:
            rows = db.read_only(
                "SELECT COUNT(*) AS n FROM information_schema.columns WHERE table_schema = DATABASE() "
                "AND table_name = 'app_user' AND column_name IN ('failed_count', 'locked_until')")
            return bool(rows) and int(rows[0]["n"]) == 2
        except Exception:
            return False

    def fail_state(self, login_id: str, user: dict | None) -> FailState:
        if user and self.has_lock_columns():
            from app.core import db
            rows = db.read_only("SELECT failed_count, locked_until FROM app_user WHERE user_id = %s",
                                (user["user_id"],))
            if rows:
                return FailState(int(rows[0]["failed_count"] or 0), rows[0]["locked_until"])
        with self._lock:
            return self._mem.get(login_id, FailState())

    def save_fail_state(self, login_id: str, user: dict | None, state: FailState) -> None:
        if user and self.has_lock_columns():
            from app.core import db
            with db.connect() as con:
                with con.cursor() as cur:
                    cur.execute("UPDATE app_user SET failed_count = %s, locked_until = %s WHERE user_id = %s",
                                (state.count, state.locked_until, user["user_id"]))
                con.commit()
            return
        with self._lock:
            self._mem[login_id] = state


def get_user_store() -> UserStore:
    return UserStore()


# ── 로그인 ───────────────────────────────────────────

def public_user(row: dict) -> dict:
    """토큰과 화면에 주는 사용자 정보. 화면 목업 publicUser {id, role, gu, org, readOnly} 모양."""
    org = " ".join(x for x in (row.get("org_name"), row.get("team_name")) if x) or None
    return {"user_id": row["user_id"], "login_id": row["login_id"], "role": ROLE_CODES.get(row.get("role") or ""),
            "role_name": row.get("role"), "gu": row.get("gu_name") or None, "org": org,
            "name": row.get("display_name")}


def authenticate(store: UserStore, login_id: str, password: str, now: datetime | None = None) -> dict:
    """맞으면 public_user(), 틀리면 ApiError(401 wrong_password / 423 locked / 403 inactive_account)."""
    now = now or datetime.now()
    login_id = (login_id or "").strip()
    user = store.get_by_login(login_id) if login_id else None
    state = store.fail_state(login_id, user)
    lock_extra = {"lock_minutes": LOCK_MINUTES}

    if state.locked_until and state.locked_until > now:
        raise ApiError(423, "account_locked", f"{MAX_FAILS}번 틀려 {LOCK_MINUTES}분 동안 잠겼습니다", lock_extra)
    if state.locked_until:                                    # 잠금 시간이 지났으면 처음부터
        state = FailState()

    ok = verify_password(password or "", user["password_hash"] if user else _DUMMY_HASH)
    if not (user and ok):
        state.count += 1
        if state.count >= MAX_FAILS:
            store.save_fail_state(login_id, user, FailState(0, now + timedelta(minutes=LOCK_MINUTES)))
            raise ApiError(423, "account_locked", f"{MAX_FAILS}번 틀려 {LOCK_MINUTES}분 동안 잠겼습니다", lock_extra)
        store.save_fail_state(login_id, user, state)
        raise ApiError(401, "wrong_password", "아이디 또는 비밀번호가 맞지 않습니다",
                       {"remaining": MAX_FAILS - state.count, **lock_extra})

    if str(user.get("is_active") or "").strip().lower() in INACTIVE:
        raise ApiError(403, "inactive_account", "사용이 중지된 계정입니다")
    pub = public_user(user)
    if pub["role"] is None:
        raise ApiError(403, "unknown_role", "역할이 정해지지 않은 계정입니다")
    if state.count:
        store.save_fail_state(login_id, user, FailState())
    return pub


# ── 기능 API에 붙이는 것 ─────────────────────────────

def current_user(request: Request) -> dict:
    """로그인 확인. 토큰이 없거나 틀리면 401. 확인한 사용자는 request.state.user에도 둔다(요청 로그가 읽음)."""
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "login_required", "로그인이 필요합니다")
    p = decode_token(token.strip())
    user = {"user_id": int(p["sub"]), "login_id": p.get("login"), "role": p.get("role"), "gu": p.get("gu"),
            "org": p.get("org"), "name": p.get("name"), "login_at": int(p["iat"]), "session": p.get("jti")}
    _check_still_valid(user)
    request.state.user = user
    return user


# ── 멈춘 계정·바뀐 역할 막기 (I-01) ────────────────────
# 토큰은 8시간 살아 있어서, 운영자가 계정을 멈추거나 역할을 바꿔도 그동안 옛 권한으로 쓸 수 있다.
# 그래서 DB가 있으면 요청마다 60 app_user를 확인한다 (같은 계정은 30초 동안 다시 읽지 않음).
_STATE_TTL = 30.0
_state_cache: dict[int, tuple[float, dict | None]] = {}
_state_lock = threading.Lock()


def forget_account_state(user_id: int | None = None) -> None:
    """계정 상태를 바꾼 뒤 부른다 (accounts_api). 다음 요청부터 바로 새 상태로 확인."""
    with _state_lock:
        if user_id is None:
            _state_cache.clear()
        else:
            _state_cache.pop(user_id, None)


def _account_state(user_id: int) -> dict | None:
    now = time.monotonic()
    with _state_lock:
        hit = _state_cache.get(user_id)
        if hit and now - hit[0] < _STATE_TTL:
            return hit[1]
    from app.core import db
    rows = db.read_only("SELECT role, gu_name, is_active FROM app_user WHERE user_id = %s", (user_id,))
    row = rows[0] if rows else None
    with _state_lock:
        _state_cache[user_id] = (now, row)
    return row


def _check_still_valid(user: dict) -> None:
    from app.core import db
    if not db.is_configured():                                  # DB 없이 도는 시험·개발 서버는 토큰만 본다
        return
    try:
        row = _account_state(user["user_id"])
    except Exception:                                           # DB가 잠깐 안 되면 토큰 확인만으로 통과 (기존과 같음)
        logger.warning("account state check skipped (db unavailable)")
        return
    if row is None or str(row.get("is_active") or "").strip().lower() in INACTIVE:
        raise ApiError(401, "account_inactive", "사용이 멈춘 계정입니다. RADAR 운영자에게 문의해 주세요")
    if ROLE_CODES.get(row.get("role") or "") != user.get("role") or (row.get("gu_name") or None) != (user.get("gu") or None):
        raise ApiError(401, "role_changed", "역할이 바뀌었습니다. 다시 로그인해 주세요")


def require_roles(*roles: str) -> Callable[..., dict]:
    """이 역할만 통과: Depends(require_roles("city", "operator")). 역할 코드: district · city · operator"""
    unknown = set(roles) - set(ROLE_NAMES)
    if unknown:
        raise ValueError(f"모르는 역할 코드: {sorted(unknown)}")

    def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise ApiError(403, "forbidden_role", "이 역할로는 쓸 수 없는 기능입니다")
        return user

    return _dep


def allowed_gus(user: dict) -> list[str]:
    """볼 수 있는 구. 구 도로관리팀은 자기 구만, 시 도로과·RADAR 운영자는 3개 구 전체."""
    if user.get("role") == "district":
        return [user["gu"]] if user.get("gu") in GU_LIST else []
    return list(GU_LIST)


def check_gu(user: dict, gu: str | None) -> None:
    """다른 구 자료를 달라고 하면 403."""
    if gu and gu not in allowed_gus(user):
        raise ApiError(403, "forbidden_gu", "담당 구가 아닌 자료입니다")


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
