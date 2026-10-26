"""실패 알림 받을 메일 (I-03, 화면명세 AD-17 '알림 설정') 저장·읽기.

저장 곳: 91 app_setting (setting_key = 'alert_emails') — SQL v2.2에는 없는 표라 은경이 추가 제안 (docs/ops/I03_alert_mail.md)
표가 아직 없으면: 읽기는 .env의 RADAR_ALERT_EMAILS(쉼표로 여러 개)로 대신하고, 저장은 '표 없음'으로 막는다.
"""
from __future__ import annotations

import os

from app.core import db

KEY = "alert_emails"


class SettingTableMissing(Exception):
    pass


class AlertSettingStore:
    def _read_db(self) -> str | None:
        rows = db.read_only("SELECT setting_value FROM app_setting WHERE setting_key = %s", (KEY,))
        return rows[0]["setting_value"] if rows else ""

    def get(self) -> tuple[str, str]:
        """(쉼표로 이은 메일, 어디서 읽었는지 'DB' / '.env')"""
        if db.is_configured():
            try:
                return self._read_db() or "", "DB"
            except Exception:
                pass                                              # 91 표가 아직 없는 DB → .env로
        return (os.getenv("RADAR_ALERT_EMAILS") or "").strip(), ".env"

    def emails(self) -> list[str]:
        from app.core.mailer import parse_emails
        return parse_emails(self.get()[0]) or []

    def save(self, value: str, user_id: int | None) -> None:
        if not db.is_configured():
            raise SettingTableMissing()
        try:
            with db.connect() as con:
                with con.cursor() as cur:
                    cur.execute("INSERT INTO app_setting (setting_key, setting_value, updated_by) VALUES (%s, %s, %s) "
                                "ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_by = VALUES(updated_by)",
                                (KEY, value, user_id))
                con.commit()
        except Exception as exc:
            if "app_setting" in str(exc) and ("doesn't exist" in str(exc) or "1146" in str(exc)):
                raise SettingTableMissing() from None
            raise


_store: AlertSettingStore = AlertSettingStore()


def set_store(store: AlertSettingStore) -> None:
    global _store
    _store = store


def get_store() -> AlertSettingStore:
    return _store
