"""시험 공통 설정 (pytest가 tests/ 안의 시험을 돌리기 전에 자동으로 읽음).

내 PC .env가 실제 DB(공용 DB 포함)를 가리켜도, 시험이 실제 DB를 읽어 막히거나 실제 DB·메일에 쓰지 않게 한다.
1) 로그인 확인(app/core/auth.py)의 '요청마다 60 app_user에서 계정 상태 다시 보기'를 끈다 (I-01).
   시험은 가짜 토큰(예: user_id 9의 운영자)으로 돌아서, 실제 DB를 보면 그 사람이 없어 401이 난다.
   시험 클래스에 REAL_ACCOUNT_CHECK = True를 두면 그 시험은 켠 채로 돈다 (tests/test_accounts_api.py StillValidTests).
2) 실행 기록(app/core/job_run.py)은 메모리에만 남긴다 (85 job_run · 86 job_run_log · 71 alert_delivery에 쓰지 않음).
   시험이 job_run.set_store(...)로 자기 저장소를 끼우면 그 저장소를 쓴다.
3) 실제 메일 서버(SMTP)로는 보내지 않는다 (I-03). 메일 시험은 각자 가짜 SMTP를 끼운다 (tests/test_alert_mail.py).
"""
import itertools
import smtplib

import pytest


class _MemoryJobStore:
    """85·86·71 대신 메모리에 남기는 실행 기록 저장소 (시험 기본값)"""

    def __init__(self):
        self._ids = itertools.count(1)
        self.runs, self.logs, self.alerts = {}, [], []

    def start(self, kind, name, module, ref_table, ref_id, triggered_by, request_id):
        rid = next(self._ids)
        self.runs[rid] = dict(job_kind=kind, job_name=name, module=module, status="실행 중")
        return rid

    def log(self, run_id, message):
        self.logs.append((run_id, message))

    def finish(self, run_id, status, row_cnt, error_code, cause, ref_table, ref_id):
        self.runs.get(run_id, {}).update(status=status)

    def alert_failure(self, run_id, message):
        self.alerts.append((run_id, message))


class _NoRealSmtp:
    def __init__(self, *a, **k):
        raise OSError("시험 중에는 실제 메일 서버로 보내지 않음 (tests/conftest.py)")


@pytest.fixture(autouse=True)
def _no_real_db_writes(request, monkeypatch):
    from app.core import auth, job_run
    if not getattr(request.cls, "REAL_ACCOUNT_CHECK", False):
        monkeypatch.setattr(auth, "_check_still_valid", lambda user: None)
    job_run.set_store(_MemoryJobStore())
    monkeypatch.setattr(smtplib, "SMTP", _NoRealSmtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _NoRealSmtp)
    yield
    job_run.set_store(_MemoryJobStore())        # 시험이 tearDown에서 실제 저장소로 되돌려도, 다음 시험 전까지 메모리로
