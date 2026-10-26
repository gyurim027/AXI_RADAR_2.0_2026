"""AI-10 조치 제안 API 독립 시험. 실제 JSON/DB를 수정하지 않음.

설치: tests/test_ai10_proposal_api.py
실행: uv run python -m tests.test_ai10_proposal_api
(패키지 구성이 다르면 $env:PYTHONPATH=(Get-Location).Path 설정 후 python으로 실행)
"""
import json
import tempfile
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.ai10_review_api import create_router


def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "review.json"
        items = {}
        def make(status, approved, text):
            return {"review_status":status, "approved":approved,"edited_template":text,
                    "revision":1,"approved_at":"TEST", "findings":[],"events":[]}
        items['CK-01'] = make('approved', True, '현장 상태를 확인하고 정비를 검토합니다.')
        items['CK-02'] = make('pending', False, '검토 대기 문장')
        items['CK-03'] = make('rejected', False, '반려 문장')
        items['CK-04'] = make('approved', False, '불일치 문장')
        items['CK-05'] = make('approved', True, '  ')
        store.write_text(json.dumps({'items': items},ensure_ascii=False), encoding='utf-8')
        before = store.read_bytes()
        app = FastAPI()
        app.include_router(create_router(store))
        client=TestClient(app)
        count=0
        def ok(name, expr):
            nonlocal count
            assert expr, name
            count+=1
            print('통과 | '+name)
        path='/api/ai10/reviews/proposals/'
        good=client.post(path+'CK-01',json={'confirmed_department':'시험 확인 부서','confirmed_legal_basis':'시험 확인 조문'})
        print("실제 API 응답:", good.status_code, good.text)
        ok('승인 문장 결과 반환',good.status_code==200 and good.json()['action_proposal_sentence']==items['CK-01']['edited_template'])
        ok('전달받은 부서·조문 보존',good.json()['receiving_department']=='시험 확인 부서' and good.json()['confirmed_legal_basis']=='시험 확인 조문')
        ok('전체 표시 가능 여부',good.json()['ready_for_full_display'] is True)
        ok('내부 검토 정보 미노출',all(x not in good.json() for x in ['events','findings','reviewer','review_note']))
        missing=client.post(path+'CK-01',json={})
        ok('누락 정보 임의 생성 방지',missing.status_code==200 and missing.json()['receiving_department'] is None and missing.json()['confirmed_legal_basis'] is None)
        ok('누락 정보 표시',missing.json()['missing_information']==['받는 부서','확인된 근거 조문'] and missing.json()['ready_for_full_display'] is False)
        ok('미승인 문장 차단',client.post(path+'CK-02',json={}).status_code==404)
        ok('반려 문장 차단',client.post(path+'CK-03',json={}).status_code==404)
        ok('상태 불일치 차단',client.post(path+'CK-04',json={}).status_code==404)
        ok('빈 승인 문장 차단',client.post(path+'CK-05',json={}).status_code==404)
        ok('존재하지 않는 CK 404',client.post(path+'CK-99',json={}).status_code==404)
        ok('기존 목록 조회 유지',client.get('/api/ai10/reviews').status_code==200)
        ok('저장소 변경 없음',store.read_bytes()==before)
        print(f'결과: {count}/{count} 통과 | 실제 JSON/DB 변경 없음')

if __name__=='__main__':
    main()
