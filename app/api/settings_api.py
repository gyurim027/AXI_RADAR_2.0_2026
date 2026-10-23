"""I-02 운영자 설정 조회. 쓰기·승인·자동 버전 선택·계산 경로는 추가하지 않는다."""
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from app.core.auth import require_roles
from app.services.settings.repository import SettingsRepository, get_repository

router = APIRouter(prefix="/api/settings/versions", tags=["산정 설정 조회 (I-02)"])
operator = require_roles("operator")


@router.get("")
def versions(kind: Literal["가중치", "기준값", "우선 확인 조건"] | None = None,
             status: Literal["제안", "승인", "돌려보냄"] | None = None,
             limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
             _user: dict = Depends(operator), repo: SettingsRepository = Depends(get_repository)):
    return repo.list_versions(kind, status, limit, offset)


@router.get("/{setting_id}")
def version(setting_id: int = Path(gt=0, le=9223372036854775807),
            _user: dict = Depends(operator), repo: SettingsRepository = Depends(get_repository)):
    return repo.get_version(setting_id)
