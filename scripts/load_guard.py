"""적재 스크립트 공통 안전장치: 로컬이 아닌 DB(공용 DB 등)에는 --allow-shared-db 없이는 쓰지 않는다."""
from __future__ import annotations

import sys

LOCAL = {"127.0.0.1", "localhost", "::1"}


def check_target(allow_shared: bool) -> str:
    from app.core.config import get_settings
    s = get_settings().db
    if not s.configured:
        sys.exit("DB 접속 정보가 없습니다. .env의 RADAR_DB_*를 확인하세요.")
    host = s.host or "(소켓)"
    local = bool(s.socket) or (s.host or "") in LOCAL
    if not local and not allow_shared:
        sys.exit(f"{host} 은(는) 로컬 DB가 아닙니다. 시험 적재는 내 PC 로컬 DB로 하세요. (공용 DB에 쓰려면 팀에 알린 뒤 --allow-shared-db)")
    return f"{host}:{s.port}/{s.name}"
