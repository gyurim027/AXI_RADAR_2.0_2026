"""실패 알림 메일 설정 API (I-03, 화면명세 AD-17 '설정 > 알림 설정'). 주소: /api/admin/alert-email · RADAR 운영자만.

GET  /api/admin/alert-email          {value: "a@x.kr, b@y.kr", source: "DB"|".env", mailReady: SMTP 설정 여부}
PUT  /api/admin/alert-email {value}  저장 (쉼표로 여러 개). 형식이 틀리면 422 format, 91 표가 없으면 503 setting_table_missing
POST /api/admin/alert-email/test     저장된 주소로 시험 메일 한 통 (SMTP 설정 확인용)

화면 목업 adminServer.js getAlertEmail·saveAlertEmail과 같은 모양 ({value} / {ok}). 저장하면 접근 기록 '설정 변경'.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core import access_audit as audit
from app.core import mailer
from app.core.auth import require_roles
from app.core.responses import ApiError
from app.services.ops.alert_settings import AlertSettingStore, SettingTableMissing, get_store

router = APIRouter(prefix="/api/admin/alert-email", tags=["실패 알림 메일 (I-03)"])
operator = require_roles("operator")
FORMAT_MSG = "메일 주소 형식이 맞지 않습니다. 예: name@example.com"       # AD-17 1-1 오류 문구


class Body(BaseModel):
    value: str


@router.get("")
def get_alert_email(_u: dict = Depends(operator), store: AlertSettingStore = Depends(get_store)):
    value, source = store.get()
    return {"value": value, "source": source, "mail_ready": mailer.is_configured()}


@router.put("")
def save_alert_email(body: Body, request: Request, user: dict = Depends(operator),
                     store: AlertSettingStore = Depends(get_store)):
    emails = mailer.parse_emails(body.value)
    if emails is None:
        raise ApiError(422, "format", FORMAT_MSG)
    try:
        store.save(", ".join(emails), user.get("user_id"))
    except SettingTableMissing:
        raise ApiError(503, "setting_table_missing", "알림 메일을 저장할 표(91 app_setting)가 아직 DB에 없습니다.") from None
    audit.record(request, user, audit.SETTING_CHANGE, key="실패 알림 받을 메일", reason="알림 설정")
    return {"ok": True, "value": ", ".join(emails), "message": "알림 메일을 저장했습니다."}


@router.post("/test")
def test_alert_email(_u: dict = Depends(operator), store: AlertSettingStore = Depends(get_store)):
    to = store.emails()
    if not to:
        raise ApiError(409, "no_recipient", "먼저 알림 받을 메일을 저장해 주세요.")
    ok, code = mailer.send(to, "[RADAR] 실패 알림 시험 메일", "RADAR 실패 알림 메일 설정을 확인하는 시험 메일입니다.")
    if not ok:
        raise ApiError(502 if code != "smtp_not_configured" else 503, code,
                       "메일 서버(.env RADAR_SMTP_*)가 설정되지 않았습니다." if code == "smtp_not_configured"
                       else "메일을 보내지 못했습니다. 메일 서버 설정을 확인해 주세요.")
    return {"ok": True, "sent": len(to)}
