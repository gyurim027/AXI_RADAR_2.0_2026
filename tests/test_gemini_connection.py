"""명시적 opt-in이 있는 경우에만 실제 Gemini 연결을 시험합니다.
기본 pytest 실행/수집에서는 네트워크 API를 호출하지 않습니다.
"""
import os
import time
from pathlib import Path
import pytest


def test_gemini_connection():
    if os.getenv('RUN_GEMINI_INTEGRATION_TESTS') != '1':
        pytest.skip('외부 API 연동 검사는 RUN_GEMINI_INTEGRATION_TESTS=1에서만 실행')
    from dotenv import load_dotenv
    from google import genai
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / '.env', override=False)
    api_key = os.getenv('GEMINI_API_KEY')
    model_name = os.getenv('GEMINI_MODEL')
    if not api_key or not model_name:
        pytest.skip('GEMINI_API_KEY 또는 GEMINI_MODEL 설정 없음')
    client = genai.Client(api_key=api_key)
    try:
        start = time.perf_counter()
        response = client.models.generate_content(
            model=model_name,
            contents=(
                '다음 상황에 대한 공공행정용 조치 제안 문장 한 개를 작성하세요.\n'
                '상황: 횡단보도 보행 녹색시간 자료가 없음.\n'
                '확인할 사항: 신호 주기표와 현장 측정.\n'
                '조건: 법령 위반이라고 단정하지 말 것.'
            ),
        )
        print('모델:', model_name)
        print(f'응답 소요 시간: {time.perf_counter() - start:.2f}초')
        print('생성 결과:', response.text or '(텍스트 응답 없음)')
        assert response.text, '모델 응답 본문 없음'
    finally:
        client.close()
