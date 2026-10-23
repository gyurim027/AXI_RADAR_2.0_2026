"""AI-03 설정. 값은 저장소 루트 .env에서만 읽는다 (app/core/config.py, W05 공통 구조 5장).

  VWORLD_KEY   브이월드 인증키 (.env.example에 있음)
  AI03_LLM     off로 두면 LLM 없이 규칙·내부 대조·브이월드만 (배치 --no-ai)
LLM은 공통 모듈 app/core/llm.py의 작업 'ai03_refine'으로 부른다 (모델·경로는 app/core/llm_tasks.toml).
기준 자료: data/ai03/ (공개 자료로 만든 작은 CSV — 01 격자, 41·50·55 이름, 35·18 등 신호 지점, 45 주소 좌표)
캐시: out/ai03/ (저장소에 올리지 않음, .gitignore)
"""
import os

from app.core.config import ROOT, get_settings

get_settings()                                   # 루트 .env를 읽어 환경변수로 넣는다

DATA = ROOT / "data" / "ai03"
OUT = ROOT / "out" / "ai03"
OUT.mkdir(parents=True, exist_ok=True)

VWORLD_KEY = os.getenv("VWORLD_KEY", "").strip()
LLM_TASK = "ai03_refine"
LLM_ENABLED = os.getenv("AI03_LLM", "on").lower() not in ("off", "none", "0")

SEONGNAM_BBOX = (127.00, 37.33, 127.20, 37.48)   # 브이월드 장소 검색 범위 (경도, 위도)
VWORLD_SLEEP = 0.15                               # 호출 간격(초) — 대량 호출은 나눠서
