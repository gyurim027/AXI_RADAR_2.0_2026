"""AI-03 좌표 결과 조회 — 위치 미확인 현황 (화면 AD-04 위치 미확인 탭). 읽기만 한다.

- data_issue(A-05·A-06·A-08)가 아니라 원천 표의 좌표가 빈 행을 직접 읽는다 (규림님 10/28: 표별 좌표 확보 현황 + 단속 건수 상위 20곳).
- 좌표 없음 = lat 또는 lon이 비어 있음. AI-03이 좌표를 채우는 4개 표만 센다.
- 표 이름은 이 파일의 고정 목록만 쓰고(사용자 입력이 아니다), 값은 %s 자리표시자로 넘긴다.
- 시설·민원의 좌표 값은 내보내지 않는다. 건수와 단속장소 이름·단속 건수만 준다.
"""
from __future__ import annotations

from app.core import db

# (표 이름, 화면 이름) — AI-03이 좌표를 채우는 표
TABLES = (
    ("src_parking_enforce_place", "단속장소"),
    ("src_signal_controller", "신호기"),
    ("src_police_signal", "경찰 신호"),
    ("src_complaint", "민원"),
)
TOP_TABLE = "src_parking_enforce_place"                 # 영향도 순위는 단속장소만 (단속 건수 칸이 있는 표)
NO_COORD = "(lat IS NULL OR lon IS NULL)"


class UnlocatedRepository:
    def coverage(self) -> list[dict]:
        """표별 (전체 행 수, 좌표 없는 행 수)."""
        out = []
        for table, label in TABLES:
            rows = db.read_only(f"SELECT COUNT(*) AS total_rows, SUM({NO_COORD}) AS missing_rows FROM {table}")
            r = rows[0] if rows else {}
            out.append({"table": table, "label": label,
                        "total_rows": int(r.get("total_rows") or 0), "missing_rows": int(r.get("missing_rows") or 0)})
        return out

    def top_missing(self, limit: int) -> list[dict]:
        """좌표가 빈 단속장소를 단속 건수가 많은 순서로."""
        return db.read_only(
            f"SELECT row_id, enforce_place, enforce_cnt FROM {TOP_TABLE} WHERE {NO_COORD} "
            "ORDER BY enforce_cnt DESC, row_id LIMIT %s", [limit])


_repo: UnlocatedRepository = UnlocatedRepository()


def set_repository(repo: UnlocatedRepository) -> None:
    """시험용: 저장소를 바꿔 끼운다."""
    global _repo
    _repo = repo


def get_repository() -> UnlocatedRepository:
    return _repo
