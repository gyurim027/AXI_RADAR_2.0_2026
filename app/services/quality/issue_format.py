"""A-05·A-06·A-08 공통 문제 목록 형식 (진이님과 맞춘 모양).

칸 (순서 고정)
  check_fn       검사 기능: A-05 / A-06 / A-08
  error_code     코드용 오류 코드 (예: A06_OUT_OF_GRID)
  검사           사람이 읽는 문제 이름
  표             v2 표 이름 (적재 전이면 비움)
  행 키          실제 PK. 'PK칸=값', 복합키는 'k1=v1;k2=v2' (없으면 비움)
  칸             문제가 있는 칸 이름 (파일 전체 문제면 비움)
  값             문제가 된 값
  사유           문제 설명·비고
  묶음 ID        A-08 같은 시설 묶음 (그 외 비움)
  원본 파일      적재 전 파일 이름 또는 원본 위치 (없으면 비움)
  원본 행 번호   원본 파일의 행 번호 (파일 전체 문제면 비움)
  upload_id      84 data_upload의 upload_id (없으면 비움 — 임의로 만들지 않음)
  찾은 시각      검사한 시각
  확인 / 처리    운영자가 채움
"""
from datetime import datetime
import pandas as pd

COLUMNS = ["check_fn", "error_code", "검사", "표", "행 키", "칸", "값", "사유", "묶음 ID",
           "원본 파일", "원본 행 번호", "upload_id", "찾은 시각", "확인", "처리"]

CODES = {  # 검사 이름 → 오류 코드
    "좌표 범위 이상": "A06_COORD_RANGE", "위경도 뒤바뀜 의심": "A06_LATLON_SWAP", "성남 격자 밖": "A06_OUT_OF_GRID",
    "gid 불일치": "A06_GID_MISMATCH", "gid 빔 (좌표 있음)": "A06_GID_MISSING", "좌표 빔 (gid 있음)": "A06_COORD_MISSING",
    "구 불일치": "A06_GU_MISMATCH", "구 불일치(경계 근처·확인 필요)": "A06_GU_NEAR_BORDER",
    "처리일 < 접수일": "A06_DATE_ORDER", "접수일이 자료 기간 밖": "A06_DATE_RANGE",
    "① 내용이 같은 행": "A08_SAME_CONTENT", "② 같은 이름·같은 자리": "A08_SAME_NAME_NEAR",
    "③ 같은 자리·다른 이름 (확인 필요)": "A08_SAME_SPOT_DIFF_NAME",
}
FIELD = {  # 검사 → 문제가 있는 칸
    "좌표 범위 이상": "lat;lon", "위경도 뒤바뀜 의심": "lat;lon", "성남 격자 밖": "lat;lon", "gid 불일치": "gid",
    "gid 빔 (좌표 있음)": "gid", "좌표 빔 (gid 있음)": "lat;lon", "구 불일치": "gu", "구 불일치(경계 근처·확인 필요)": "gu",
    "처리일 < 접수일": "processed_date", "접수일이 자료 기간 밖": "received_date",
}


def to_issue(df: pd.DataFrame, check_fn: str, pk: dict) -> pd.DataFrame:
    """표·행 키·검사·값·비고(·묶음 ID) 목록을 공통 형식으로. pk: {표 이름: PK 칸 이름}."""
    now = datetime.now().isoformat(timespec="seconds")
    out = pd.DataFrame({
        "check_fn": check_fn,
        "error_code": df["검사"].map(CODES).fillna(f"{check_fn.replace('-', '')}_OTHER"),
        "검사": df["검사"],
        "표": df["표"],
        "행 키": [f"{pk.get(t, 'key')}={k}" for t, k in zip(df["표"], df["행 키"])],
        "칸": df["검사"].map(FIELD).fillna(""),
        "값": df.get("값", ""),
        "사유": df.get("비고", ""),
        "묶음 ID": df.get("묶음 ID", ""),
        "원본 파일": df.get("원본 파일", ""),
        "원본 행 번호": df.get("원본 행 번호", ""),
        "upload_id": df.get("upload_id", ""),
        "찾은 시각": now,
        "확인": "", "처리": "",
    })
    return out[COLUMNS]
