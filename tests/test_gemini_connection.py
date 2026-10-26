
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")

if not model_name:
    raise RuntimeError("GEMINI_MODEL이 설정되지 않았습니다.")

client = genai.Client(api_key=api_key)

try:
    # ① AI 호출 시작 시간
    start = time.perf_counter()

    # ② Gemini API 호출
    response = client.models.generate_content(
        model=model_name,
        contents=(
            "다음 상황에 대한 공공행정용 조치 제안 문장 "
            "한 개를 작성하세요.\n"
            "상황: 횡단보도 보행 녹색시간 자료가 없음.\n"
            "확인할 사항: 신호 주기표와 현장 측정.\n"
            "조건: 법령 위반이라고 단정하지 말 것."
        ),
    )

    # ③ 응답 완료 시간 계산
    elapsed = time.perf_counter() - start

    # ④ 결과 출력
    print("모델:", model_name)
    print(f"응답 소요 시간: {elapsed:.2f}초")
    print("생성 결과:")
    print(response.text or "(텍스트 응답 없음)")

finally:
    client.close()
