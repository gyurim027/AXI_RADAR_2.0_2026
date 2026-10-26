"""실패 알림 메일 (I-03) — 기능정의서 v0.5.3 I-03 "어드민 알림과 RADAR 운영자가 정한 메일로 보낸다", 화면명세 AD-17.

보내는 곳: .env의 SMTP 설정 (키·비밀번호는 .env에만, 저장소·채팅·문서에 쓰지 않음)
    RADAR_SMTP_HOST=            # 비우면 메일을 보내지 않음 (화면 알림만)
    RADAR_SMTP_PORT=587
    RADAR_SMTP_USER=
    RADAR_SMTP_PASSWORD=
    RADAR_SMTP_FROM=            # 보내는 사람 주소 (비우면 RADAR_SMTP_USER)
    RADAR_SMTP_TLS=starttls     # starttls / ssl / none
받는 곳: 어드민 '알림 설정'(AD-17)에서 RADAR 운영자가 정한 메일 (app/services/ops/alert_settings.py)

메일에는 실행 이름·번호·실패 원인 한 줄만 넣는다 (85 job_run.cause와 같은 글 — 원문·개인정보·SQL 없음).
메일이 실패해도 작업·화면 알림은 그대로다. 결과는 그 실행의 단계 기록(86)에 한 줄 남는다.
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
import threading
from email.message import EmailMessage

logger = logging.getLogger("radar.mail")
EMAIL = re.compile(r"^[^\s@,]+@[^\s@,]+\.[^\s@,]+$")
TIMEOUT_S = 10


def parse_emails(value: str | None) -> list[str] | None:
    """'a@x.kr, b@y.kr' → 목록. 하나라도 형식이 틀리거나 비어 있으면 None (AD-17 오류 문구)."""
    items = [x.strip() for x in str(value or "").split(",") if x.strip()]
    if not items or not all(EMAIL.match(x) for x in items):
        return None
    return list(dict.fromkeys(items))


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    return bool(_env("RADAR_SMTP_HOST"))


def send(to: list[str], subject: str, body: str) -> tuple[bool, str | None]:
    """메일 한 통. (보냄 여부, 실패 코드). 실패 이유 글자(서버 응답)는 밖으로 내보내지 않는다."""
    if not to:
        return False, "no_recipient"
    if not is_configured():
        return False, "smtp_not_configured"
    host, port = _env("RADAR_SMTP_HOST"), int(_env("RADAR_SMTP_PORT", "587") or 587)
    user, password = _env("RADAR_SMTP_USER"), os.getenv("RADAR_SMTP_PASSWORD") or ""
    tls = _env("RADAR_SMTP_TLS", "starttls").lower()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, _env("RADAR_SMTP_FROM") or user, ", ".join(to)
    msg.set_content(body)
    try:
        if tls == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_S, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=TIMEOUT_S)
        with server:
            if tls == "starttls":
                server.starttls(context=ssl.create_default_context())
            if user:
                server.login(user, password)
            server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "smtp_auth_failed"
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("실패 알림 메일을 보내지 못했습니다: %s", type(exc).__name__)
        return False, "smtp_failed"


# ── 실패 알림 (job_run._fail에서 부름) ─────────────────────────

ASYNC = True          # 작업을 기다리게 하지 않으려고 따로 보냄. 시험에서는 False


def _send_failure(run_id: int, job_name: str, cause: str | None, log) -> None:
    from app.services.ops.alert_settings import get_store
    try:
        to = get_store().emails()
    except Exception:
        to = []
    if not to:
        return                                                     # 받을 메일을 정하지 않음 → 화면 알림만
    subject = f"[RADAR] 실행 실패: {job_name}"
    body = (f"RADAR 실행이 실패했습니다.\n\n실행: {job_name} (실행 번호 {run_id})\n원인: {cause or '-'}\n\n"
            "어드민 > 산정 > 실행 기록에서 로그를 보고 다시 실행해 주세요.\n"
            "이 메일은 어드민 > 설정 > 알림 설정에 적힌 주소로 보냈습니다.")
    ok, code = send(to, subject, body)
    log(f"실패 알림 메일: {len(to)}곳에 보냄" if ok else f"실패 알림 메일을 보내지 못함 ({code}) — 화면 알림은 남아 있음")


def notify_failure(run_id: int, job_name: str, cause: str | None, log) -> None:
    if ASYNC:
        threading.Thread(target=_send_failure, args=(run_id, job_name, cause, log), daemon=True).start()
    else:
        _send_failure(run_id, job_name, cause, log)
