"""로그인 API (I-01). 주소: /api/auth/...

POST /api/auth/login   {"loginId": "...", "password": "..."}
    성공 200 {"token", "tokenType": "Bearer", "expiresIn"(초), "user": {"id", "role", "gu", "org", "name", "readOnly"}}
    틀림 401 wrong_password (+ remaining 남은 횟수, lockMinutes) · 잠김 423 account_locked · 중지 403 inactive_account
GET  /api/auth/me      지금 토큰의 사용자 (화면 새로고침 때)

로그아웃은 화면이 토큰을 버리면 된다 (서버에 남기는 세션 없음). 성공한 로그인은 70 access_audit에 한 줄.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core import access_audit as audit
from app.core.auth import UserStore, authenticate, current_user, get_user_store, make_token

router = APIRouter(prefix="/api/auth", tags=["AUTH 로그인"])


class LoginBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    login_id: str = Field(alias="loginId", min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def _screen_user(u: dict) -> dict:
    # 화면 목업 publicUser 모양: id = 로그인 아이디
    return {"id": u["login_id"], "role": u["role"], "gu": u.get("gu"), "org": u.get("org"),
            "name": u.get("name"), "read_only": False}


@router.post("/login")
def login(body: LoginBody, request: Request, store: UserStore = Depends(get_user_store)):
    user = authenticate(store, body.login_id, body.password)
    token, expires_in = make_token(user)
    request.state.user = {"user_id": user["user_id"], "role": user["role"]}      # 요청 로그용
    audit.record(request, user, audit.LOGIN, key=None, reason="로그인")
    return {"token": token, "token_type": "Bearer", "expires_in": expires_in, "user": _screen_user(user)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": _screen_user(user)}
