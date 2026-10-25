"""계정 관리(I-01)·접속 기록 조회(I-04) API. 주소: /api/admin/... · RADAR 운영자만. SQL v2.1~ (60·61·70).

화면 목업(frontend/src/mocks/adminServer.js)과 같은 모양으로 돌려준다.
GET   /api/admin/accounts                         계정 목록 + 권한 변경 기록 + 역할 목록 (listAccounts)
POST  /api/admin/accounts                         계정 만들기 {role, gu, team, name, loginId} (createAccount)
                                                  → 임시 비밀번호를 한 번만 돌려준다 (DB에는 해시만)
PATCH /api/admin/accounts/{loginId}/status        사용 멈추기·다시 쓰기 {status: "멈춤" | "사용 중"} (setAccountStatus)
PATCH /api/admin/accounts/{loginId}/role          역할·담당 구 바꾸기 {role, gu, reason}
POST  /api/admin/accounts/{loginId}/password-reset  임시 비밀번호 다시 만들기 (잠금도 풂)
GET   /api/admin/access?days=30&accountId=&action=  접속 기록 (listAccess) — 읽기만

지키는 것
- 권한을 주고·바꾸고·거둘 때마다 61 role_change_log 한 줄 (3년 이상 보관, POL-022)
- 계정을 바꾸는 일은 70 access_audit에 '설정 변경'으로 남긴다
- 내 계정은 멈추거나 역할을 바꿀 수 없다 (운영자가 아무도 없게 되는 것을 막음)
- 비밀번호 원문은 저장·기록하지 않는다. 임시 비밀번호는 응답으로 한 번만 준다
"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core import access_audit as audit
from app.core.auth import GU_LIST, ROLE_CODES, forget_account_state, hash_password, require_roles
from app.core.responses import ApiError
from app.services.accounts.repository import AccountRepository, get_repository

router = APIRouter(prefix="/api/admin", tags=["계정·접속 기록 (I-01·I-04)"])
operator = require_roles("operator")

ROLE_OPTIONS = ["시 도로과", "구 도로관리팀", "RADAR 운영자"]        # 목업 adminData.ROLE_OPTIONS와 같은 순서
DEFAULT_TEAM = {"구 도로관리팀": "도로관리팀", "시 도로과": "도로관리팀", "RADAR 운영자": "RADAR 운영팀"}
INACTIVE = {"n", "no", "0", "false", "아니오", "사용 안 함", "중지"}


def _dot(v, with_time: bool = False):
    if not isinstance(v, datetime):
        return v or "-"
    return v.strftime("%Y.%m.%d %H:%M" if with_time else "%Y.%m.%d")


def _active(row: dict) -> bool:
    return str(row.get("is_active") or "").strip().lower() not in INACTIVE


def _temp_password() -> str:
    return secrets.token_urlsafe(9)                              # 12자, 기록에 남기지 않음


def _org(role: str, gu: str | None, team: str) -> tuple[str, str]:
    """(org_name, team_name). 화면 소속 = org_name + ' ' + team_name (로그인 응답 user.org)."""
    if role == "구 도로관리팀":
        return f"{gu} 건설과", team
    if role == "시 도로과":
        return "성남시 도로과", team
    return "RADAR", team


def _check_role(role: str, gu: str | None) -> str | None:
    if role not in ROLE_CODES:
        raise ApiError(400, "invalid_role", "역할은 " + " · ".join(ROLE_OPTIONS) + " 중 하나입니다")
    if role == "구 도로관리팀":
        if gu not in GU_LIST:
            raise ApiError(400, "gu_required", "구 도로관리팀은 담당 구(수정구·중원구·분당구)를 골라야 합니다")
        return gu
    return None                                                  # 시 도로과·운영자는 3개 구 전체 → 구 비움


def _role_text(role, gu) -> str:
    if not role:
        return "-"
    return f"{role} ({gu})" if gu else role


# ── 계정 ──────────────────────────────────────────

@router.get("/accounts")
def list_accounts(limit: int = Query(200, ge=1, le=1000), _u: dict = Depends(operator),
                  repo: AccountRepository = Depends(get_repository)):
    rows = [{"id": r["login_id"], "name": r.get("display_name"), "role": r.get("role"), "gu": r.get("gu_name") or "-",
             "team": r.get("team_name") or "-", "status": "사용 중" if _active(r) else "멈춤",
             "last": _dot(r.get("last_login_at"))} for r in repo.list_accounts()]
    log = [{"id": f"rl-{r['role_change_id']}", "at": r["changed_at"].strftime("%Y-%m-%d") if r.get("changed_at") else None,
            "name": r.get("target_name") or r.get("target_login"), "from": _role_text(r.get("old_role"), r.get("old_gu_name")),
            "to": _role_text(r.get("new_role"), r.get("new_gu_name")), "by": r.get("by_name") or "-",
            "reason": r.get("reason")} for r in repo.role_log(limit)]
    return {"rows": rows, "log": log, "roles": ROLE_OPTIONS}


class CreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    role: str = Field(max_length=20)
    gu: str | None = Field(default=None, max_length=10)
    team: str | None = Field(default=None, max_length=100)
    name: str = Field(default="", max_length=100)
    login_id: str = Field(default="", alias="loginId", max_length=100)


@router.post("/accounts")
def create_account(body: CreateBody, request: Request, user: dict = Depends(operator),
                   repo: AccountRepository = Depends(get_repository)):
    gu = _check_role(body.role, body.gu)
    name, login_id = body.name.strip(), body.login_id.strip()
    if not name or not login_id:
        raise ApiError(400, "required", "이름과 아이디를 적어 주세요")
    if repo.get_account(login_id):
        raise ApiError(409, "duplicate", "이미 있는 아이디입니다")
    team = (body.team or "").strip() or DEFAULT_TEAM[body.role]
    org, team = _org(body.role, gu, team)
    temp = _temp_password()
    try:
        repo.create_account({"login_id": login_id, "name": name, "org": org, "team": team, "gu": gu, "role": body.role},
                            hash_password(temp), user["user_id"], "계정 만들기")
    except ValueError:
        raise ApiError(409, "duplicate", "이미 있는 아이디입니다") from None
    audit.record(request, user, audit.SETTING_CHANGE, key=f"계정 만들기 {login_id}", reason="계정 관리")
    return {"ok": True, "id": login_id, "temp_password": temp,
            "notice": "임시 비밀번호는 지금 한 번만 보입니다. 받는 분께 직접 전해 주세요."}


class StatusBody(BaseModel):
    status: str = Field(pattern="^(멈춤|사용 중)$")
    reason: str | None = Field(default=None, max_length=200)


@router.patch("/accounts/{login_id}/status")
def set_status(login_id: str, body: StatusBody, request: Request, user: dict = Depends(operator),
               repo: AccountRepository = Depends(get_repository)):
    acc = repo.get_account(login_id)
    if not acc:
        raise ApiError(404, "account_not_found", "계정을 찾을 수 없습니다")
    if acc["user_id"] == user["user_id"]:
        raise ApiError(403, "self_change", "내 계정은 멈출 수 없습니다")
    active = body.status == "사용 중"
    if _active(acc) == active:
        return {"ok": True, "changed": False}
    repo.set_active(acc, active, user["user_id"], body.reason or ("다시 쓰기" if active else "사용 멈추기"))
    forget_account_state(acc["user_id"])                       # 멈춘 계정은 다음 요청부터 바로 막힘
    audit.record(request, user, audit.SETTING_CHANGE,
                 key=f"계정 {'다시 쓰기' if active else '사용 멈추기'} {login_id}", reason="계정 관리")
    return {"ok": True, "changed": True}


class RoleBody(BaseModel):
    role: str = Field(max_length=20)
    gu: str | None = Field(default=None, max_length=10)
    reason: str = Field(min_length=1, max_length=200)


@router.patch("/accounts/{login_id}/role")
def change_role(login_id: str, body: RoleBody, request: Request, user: dict = Depends(operator),
                repo: AccountRepository = Depends(get_repository)):
    acc = repo.get_account(login_id)
    if not acc:
        raise ApiError(404, "account_not_found", "계정을 찾을 수 없습니다")
    if acc["user_id"] == user["user_id"]:
        raise ApiError(403, "self_change", "내 계정의 역할은 바꿀 수 없습니다")
    gu = _check_role(body.role, body.gu)
    if acc.get("role") == body.role and (acc.get("gu_name") or None) == gu:
        return {"ok": True, "changed": False}
    repo.change_role(acc, body.role, gu, user["user_id"], body.reason)
    forget_account_state(acc["user_id"])                       # 옛 토큰은 다음 요청부터 '다시 로그인'
    audit.record(request, user, audit.SETTING_CHANGE, key=f"역할 바꾸기 {login_id}", reason="계정 관리")
    return {"ok": True, "changed": True}


@router.post("/accounts/{login_id}/password-reset")
def reset_password(login_id: str, request: Request, user: dict = Depends(operator),
                   repo: AccountRepository = Depends(get_repository)):
    acc = repo.get_account(login_id)
    if not acc:
        raise ApiError(404, "account_not_found", "계정을 찾을 수 없습니다")
    temp = _temp_password()
    repo.set_password(acc["user_id"], hash_password(temp))
    audit.record(request, user, audit.SETTING_CHANGE, key=f"비밀번호 다시 만들기 {login_id}", reason="계정 관리")
    return {"ok": True, "id": login_id, "temp_password": temp,
            "notice": "임시 비밀번호는 지금 한 번만 보입니다. 받는 분께 직접 전해 주세요."}


# ── 접속 기록 (읽기만) ─────────────────────────────

@router.get("/access")
def list_access(days: int = Query(30, ge=1, le=800), account_id: str | None = Query(None, alias="accountId"),
                action: str | None = None, limit: int = Query(500, ge=1, le=5000), _u: dict = Depends(operator),
                repo: AccountRepository = Depends(get_repository)):
    if account_id in ("", "전체"):
        account_id = None
    if action in (None, "", "전체"):
        action = None
    elif action not in audit.KINDS:
        raise ApiError(400, "invalid_action", "무슨 일은 " + " · ".join(audit.KINDS) + " 중 하나입니다")
    accounts = repo.list_accounts()
    rows = []
    for r in repo.list_access(days, account_id, action, limit):
        actor = " ".join(x for x in (r.get("org_name"), r.get("team_name")) if x) or "-"
        rows.append({"id": r["access_audit_id"],
                     "at": r["accessed_at"].isoformat(timespec="seconds") if r.get("accessed_at") else None,
                     "at_label": _dot(r.get("accessed_at"), with_time=True), "actor": actor,
                     "account_id": r.get("login_id"), "who": f"{r.get('display_name') or r.get('login_id') or '-'} ({actor})",
                     "ip": r.get("client_ip") or "-", "action": r.get("resource_kind"),
                     "target": r.get("resource_key") or "-", "reason": r.get("access_reason") or "-"})
    return {"actions": list(audit.KINDS),
            "accounts": [{"value": a["login_id"],
                          "label": f"{a.get('display_name') or a['login_id']} "
                                   f"({' '.join(x for x in (a.get('org_name'), a.get('team_name')) if x)})"}
                         for a in accounts],
            "rows": rows}
