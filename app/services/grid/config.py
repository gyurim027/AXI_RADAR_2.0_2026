"""격자·검사 기능 설정 (B-01~07 · C-07 · F-02 · A-06 · A-08, 세은). 값은 루트 .env에서만 읽는다.

  RADAR_GRID_RAW_DIR  원본 공간 자료 폴더 ('최종사용할 데이터' — B100 격자 zip, 행정동 경계, 성남_링크·노드 shp,
                      경사 tif 등). 공개 자료지만 크고(약 350MB) 원본이라 저장소에 올리지 않는다.
  RADAR_V2_CSV_DIR    (선택) DB 대신 v2 통합테이블 CSV 폴더를 읽을 때. 비우면 공용 DB(app/core/db.py)를 읽는다.
"""
import os
from pathlib import Path

from app.core.config import ROOT, get_settings

get_settings()

RAW_DIR = Path(os.getenv("RADAR_GRID_RAW_DIR", "") or ROOT / "data" / "private" / "grid_raw")
V2_CSV_DIR = Path(os.environ["RADAR_V2_CSV_DIR"]) if os.getenv("RADAR_V2_CSV_DIR") else None
DATA_DIR = ROOT / "data" / "grid"
OUT_DIR = ROOT / "out" / "grid"
OUT_DIR.mkdir(parents=True, exist_ok=True)
