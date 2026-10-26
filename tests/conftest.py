"""시험 공통 설정 (pytest가 tests/ 안의 시험을 돌리기 전에 자동으로 읽음).

로그인 확인(app/core/auth.py)은 .env에 공용 DB가 설정돼 있으면 요청마다 60 app_user에서 계정 상태를 다시 본다(I-01, 멈춘 계정·바뀐 역할 막기).
시험은 가짜 토큰(예: user_id 9의 운영자)으로 돌기 때문에, 내 PC .env가 실제 DB를 가리키면 그 사람이 DB에 없어서 401이 난다.
→ 시험에서는 이 '계정 상태 다시 보기'만 끈다. 시험 클래스에 REAL_ACCOUNT_CHECK = True를 두면 그 시험은 켠 채로 돈다
  (tests/test_accounts_api.py StillValidTests — 가짜 DB 값으로 막히는지 확인).
"""
import pytest


@pytest.fixture(autouse=True)
def _no_live_account_check(request, monkeypatch):
    if getattr(request.cls, "REAL_ACCOUNT_CHECK", False):
        return
    from app.core import auth
    monkeypatch.setattr(auth, "_check_still_valid", lambda user: None)
