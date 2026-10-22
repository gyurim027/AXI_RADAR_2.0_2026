"""공통 설정 (W05-03 골격 2번).

값은 저장소 루트의 .env 또는 환경변수에서만 읽는다. 코드·문서·GitHub에 실제 값을 적지 않는다.
이름 목록과 예시는 .env.example 참고.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 저장소 루트


def _load_dotenv() -> None:
    """루트 .env를 읽는다. 이미 있는 환경변수는 덮어쓰지 않는다 (터미널에서 넣은 값이 우선)."""
    try:
        from dotenv import load_dotenv
    except ImportError:                              # python-dotenv가 없어도 환경변수만으로 동작
        return
    load_dotenv(ROOT / ".env", override=False)


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class DbSettings:
    host: str | None
    port: int
    user: str
    password: str = field(repr=False)                # 출력·로그에 비밀번호가 나오지 않게
    name: str
    socket: str | None = None
    connect_timeout: int = 5
    read_timeout: int = 30

    @property
    def configured(self) -> bool:
        """DB 주소(또는 소켓)와 계정이 있어야 연결을 시도한다."""
        return bool((self.host or self.socket) and self.user)


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret: str = field(repr=False)              # 토큰 서명 키. 비면 서버를 켤 때마다 임시 키(dev만)
    token_hours: float = 8.0                         # 로그인 토큰 유효 시간


@dataclass(frozen=True)
class Settings:
    db: DbSettings
    cors_origins: list[str]
    app_env: str                                     # dev / demo
    auth: AuthSettings = AuthSettings(jwt_secret="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()
    env = os.environ
    db = DbSettings(
        host=env.get("RADAR_DB_HOST") or None,
        port=int(env.get("RADAR_DB_PORT", "3306")),
        user=env.get("RADAR_DB_USER", ""),
        password=env.get("RADAR_DB_PASSWORD", ""),
        name=env.get("RADAR_DB_NAME", "mysqlteam02db"),
        socket=env.get("RADAR_DB_SOCKET") or None,
        connect_timeout=int(env.get("RADAR_DB_CONNECT_TIMEOUT", "5")),
        read_timeout=int(env.get("RADAR_DB_READ_TIMEOUT", "30")),
    )
    origins = _split(env.get("RADAR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    auth = AuthSettings(jwt_secret=env.get("RADAR_JWT_SECRET", ""),
                        token_hours=float(env.get("RADAR_TOKEN_HOURS", "8")))
    return Settings(db=db, cors_origins=origins, app_env=env.get("RADAR_APP_ENV", "dev"), auth=auth)
