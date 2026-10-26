"""D-10 개발 전용 API 라우터. 인증/운영 저장 미연동이므로 운영 앱에 자동 등록하지 않음."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from app.services.d10_rounds import RoundStore, RoundError

router = APIRouter(prefix='/dev/d10/rounds', tags=['D-10 개발용'])
store = RoundStore()


class CreateRequest(BaseModel):
    name: str
    kind: Literal['연간', '반기 참고']


class OpenRequest(BaseModel):
    calculation_completed: bool
    missing_sources: list[str] = []
    unevaluated_areas: list[str] = []


def apply(fn):
    try:
        return fn()
    except RoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('')
def create_round(data: CreateRequest):
    return apply(lambda: store.create(data.name, data.kind))


@router.get('')
def list_rounds():
    return store.list_all()


@router.get('/{temporary_id}')
def get_round(temporary_id: str):
    return apply(lambda: store.get(temporary_id))


@router.post('/{temporary_id}/open-preview')
def preview_round(temporary_id: str, data: OpenRequest):
    return apply(lambda: store.preview_open(temporary_id, **data.model_dump()))


@router.post('/{temporary_id}/open')
def open_round(temporary_id: str, data: OpenRequest):
    return apply(lambda: store.open(temporary_id, **data.model_dump()))
