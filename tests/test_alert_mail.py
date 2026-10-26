"""실패 알림 메일 (I-03, AD-17) 시험 — 실제 메일 서버·DB 없이. 실행: uv run python -m pytest tests/test_alert_mail.py"""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.core import access_audit, job_run, mailer
from app.core.auth import make_token
from app.core.job_run import JobFailed, track
from app.main import app
from app.services.ops import alert_settings
from tests.test_core_ops import MemoryJobStore


class FakeSmtp:
    sent = []

    def __init__(self, host, port, timeout=None, **kw):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSmtp.sent.append(msg)


class MemorySettings(alert_settings.AlertSettingStore):
    def __init__(self, value="", table=True):
        self.value, self.table = value, table

    def get(self):
        return self.value, "DB"

    def save(self, value, user_id):
        if not self.table:
            raise alert_settings.SettingTableMissing()
        self.value = value


class Audit(access_audit.AuditStore):
    rows = []

    def insert(self, actor_ref, kind, key, ip, reason):
        Audit.rows.append((kind, key, reason))


SMTP_ENV = {"RADAR_SMTP_HOST": "smtp.example.test", "RADAR_SMTP_PORT": "587", "RADAR_SMTP_USER": "radar@example.test",
            "RADAR_SMTP_PASSWORD": "x", "RADAR_SMTP_TLS": "starttls"}


class MailTests(unittest.TestCase):
    def setUp(self):
        FakeSmtp.sent.clear()
        mailer.ASYNC = False
        self.jobs = MemoryJobStore()
        job_run.set_store(self.jobs)

    def tearDown(self):
        mailer.ASYNC = True
        job_run.set_store(job_run.JobStore())
        alert_settings.set_store(alert_settings.AlertSettingStore())

    def test_parse_emails(self):
        self.assertEqual(mailer.parse_emails(" a@x.kr, b@y.kr ,a@x.kr"), ["a@x.kr", "b@y.kr"])
        for bad in ("", "a@x", "a@x.kr, 이상한", "a b@x.kr"):
            self.assertIsNone(mailer.parse_emails(bad))

    def test_failure_sends_mail_and_logs(self):
        alert_settings.set_store(MemorySettings("ops@example.test, lead@example.test"))
        with mock.patch.dict(os.environ, SMTP_ENV), mock.patch("smtplib.SMTP", FakeSmtp):
            with self.assertRaises(JobFailed):
                with track("산정", "2028 연간 산정"):
                    raise JobFailed("missing_column", "보도 면적 열이 비어 있음")
        self.assertEqual(len(self.jobs.alerts), 1)                            # 화면 알림은 그대로
        msg = FakeSmtp.sent[0]
        self.assertEqual((msg["Subject"], msg["To"]), ("[RADAR] 실행 실패: 2028 연간 산정", "ops@example.test, lead@example.test"))
        self.assertIn("보도 면적 열이 비어 있음", msg.get_content())
        self.assertEqual(self.jobs.logs[-1]["message"], "실패 알림 메일: 2곳에 보냄")

    def test_no_smtp_keeps_screen_alert(self):
        alert_settings.set_store(MemorySettings("ops@example.test"))
        with mock.patch.dict(os.environ, {"RADAR_SMTP_HOST": ""}):
            with self.assertRaises(RuntimeError):
                with track("수집", "공공데이터 수집"):
                    raise RuntimeError("boom")
        self.assertEqual(len(self.jobs.alerts), 1)
        self.assertIn("smtp_not_configured", self.jobs.logs[-1]["message"])
        self.assertEqual(FakeSmtp.sent, [])

    def test_no_recipient_no_mail(self):
        alert_settings.set_store(MemorySettings(""))
        with mock.patch.dict(os.environ, SMTP_ENV), mock.patch("smtplib.SMTP", FakeSmtp):
            with self.assertRaises(JobFailed):
                with track("산정", "산정"):
                    raise JobFailed("x", "y")
        self.assertEqual((FakeSmtp.sent, self.jobs.logs), ([], []))


class AlertEmailApiTests(unittest.TestCase):
    def setUp(self):
        Audit.rows.clear()
        access_audit.set_store(Audit())
        self.store = MemorySettings("old@example.test")
        alert_settings.set_store(self.store)
        self.c = TestClient(app, base_url="http://127.0.0.1:8000")
        tok, _ = make_token({"user_id": 3, "login_id": "operator", "role": "operator", "gu": None})
        self.h = {"Authorization": "Bearer " + tok}

    def tearDown(self):
        access_audit.set_store(access_audit.AuditStore())
        alert_settings.set_store(alert_settings.AlertSettingStore())

    def test_operator_only(self):
        tok, _ = make_token({"user_id": 4, "login_id": "city", "role": "city", "gu": None})
        self.assertEqual(self.c.get("/api/admin/alert-email", headers={"Authorization": "Bearer " + tok}).status_code, 403)

    def test_get_and_save(self):
        self.assertEqual(self.c.get("/api/admin/alert-email", headers=self.h).json()["value"], "old@example.test")
        r = self.c.put("/api/admin/alert-email", json={"value": "a@example.test,  b@example.test"}, headers=self.h)
        self.assertEqual((r.status_code, r.json()["message"]), (200, "알림 메일을 저장했습니다."))
        self.assertEqual(self.store.value, "a@example.test, b@example.test")
        self.assertIn(("설정 변경", "실패 알림 받을 메일", "알림 설정"), Audit.rows)

    def test_bad_format_and_missing_table(self):
        r = self.c.put("/api/admin/alert-email", json={"value": "name@"}, headers=self.h)
        self.assertEqual((r.status_code, r.json()["error"]["message"]), (422, "메일 주소 형식이 맞지 않습니다. 예: name@example.com"))
        self.store.table = False
        r = self.c.put("/api/admin/alert-email", json={"value": "a@example.test"}, headers=self.h)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (503, "setting_table_missing"))

    def test_test_mail(self):
        with mock.patch.dict(os.environ, {"RADAR_SMTP_HOST": ""}):
            r = self.c.post("/api/admin/alert-email/test", headers=self.h)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (503, "smtp_not_configured"))
        with mock.patch.dict(os.environ, SMTP_ENV), mock.patch("smtplib.SMTP", FakeSmtp):
            r = self.c.post("/api/admin/alert-email/test", headers=self.h)
        self.assertEqual(r.json(), {"ok": True, "sent": 1})


if __name__ == "__main__":
    unittest.main()
