"""AI-07 새 문장 틀의 가상 입력 API. 실제 데이터·AI 연결 완료 API가 아님.

부모 ai07 router의 로컬 제한을 상속한다. 실제 권한/DB 계약 확정 전에는
synthetic 계약만 허용한다. 공통 서버·설정은 수정하지 않는다.
"""
from typing import Any
from fastapi import APIRouter, Body, Request
from app.core.responses import ApiError
from app.services.ai07.e02 import explain_card
from app.services.ai07.e03 import refine_card
from app.services.ai07.f06 import build_request
from app.services.ai07.h04 import build_report

router=APIRouter()
MAX_BYTES=1024*1024


async def invoke(request, payload, action):
    if len(await request.body())>MAX_BYTES:
        raise ApiError(413,'too_large','요청 자료가 너무 큽니다')
    try:
        result=action(payload)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,AttributeError):
        raise ApiError(400,'invalid_synthetic_input','가상 시험 자료의 형식을 확인해 주세요') from None
    if result.get('status')=='blocked':
        # 프로그램 설명 상태를 반환한다. 사용자 입력/예외 상세는 오류에 붙이지 않는다.
        raise ApiError(400,'synthetic_generation_blocked','입력 조건이 맞지 않아 생성을 보류했습니다')
    return result


@router.post('/synthetic/explanation',summary='가상 근거 카드로 기본 설명문 만들기')
async def explanation(request:Request,payload:dict[str,Any]=Body(...)):
    return await invoke(request,payload,explain_card)


@router.post('/synthetic/refine',summary='가상 설명문의 제한된 표현 변경 검사 (AI 미호출)')
async def refine(request:Request,payload:dict[str,Any]=Body(...)):
    def generate(body):
        if set(body) not in ({'card'},{'card','proposed_text'}):raise ValueError('invalid_fields')
        return refine_card(body['card'],body.get('proposed_text'))
    return await invoke(request,payload,generate)


@router.post('/synthetic/request',summary='가상 자료로 관할 요청안 문장 틀 만들기 (발송 없음)')
async def request_draft(request:Request,payload:dict[str,Any]=Body(...)):
    return await invoke(request,payload,build_request)


@router.post('/synthetic/report',summary='가상 자료로 연간 검토 보고서 문장 틀 만들기 (AI 미호출)')
async def report(request:Request,payload:dict[str,Any]=Body(...)):
    return await invoke(request,payload,build_report)
