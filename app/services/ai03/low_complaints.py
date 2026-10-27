"""AI-03 좌표 결과 조회 — 좌표 정확도 '낮음' 민원 목록 (79 src_complaint ← 05 grid_feature, SQL v2.1). 읽기만 한다.

- 좌표는 AI-03 좌표 반영 단계가 79에 쓴다. 여기서는 정확도(coord_accuracy)가 '낮음'인 민원을 읽어 화면(AD-04 낮음 민원·지도)에 준다.
  '낮음' = 정확한 주소 좌표가 아님: 장소 이름 검색·내부 대조로 찾은 근처 건물 좌표, 민원 본문의 위치값 등 (v2.1 기준 354건).
- 구는 05 grid_feature.id_gu('성남시 분당구')에서 '성남시 '를 뗀 이름 (우선순위 조회와 같은 방식).
  구가 비어 있는 격자의 민원은 gu=None이고, 시 도로과·RADAR 운영자만 본다.
- 값은 항상 %s 자리표시자로 넘긴다.
"""
from __future__ import annotations

from app.core import db

COLS = ("complaint_id", "source_type", "received_date", "location_text", "admin_dong_name", "gid", "lat", "lon",
        "coord_method", "coord_accuracy")
LOW = "낮음"

_GU = "NULLIF(REPLACE(f.id_gu, '성남시 ', ''), '')"          # '성남시 분당구' → '분당구'


class LowComplaintRepository:
    def list_low(self, gus: list[str] | None, include_no_gu: bool, limit: int, offset: int) -> tuple[list[dict], int]:
        """gus=None이면 구 제한 없음. include_no_gu=False면 구가 빈 격자의 민원은 뺀다(구 도로관리팀)."""
        where = ["c.coord_accuracy = %s"]
        args: list = [LOW]
        if gus is not None:
            gu_cond = f"{_GU} IN ({', '.join(['%s'] * len(gus))})" if gus else "FALSE"
            args.extend(gus)
            where.append(f"({gu_cond} OR {_GU} IS NULL)" if include_no_gu else gu_cond)
        elif not include_no_gu:
            where.append(f"{_GU} IS NOT NULL")
        base = "FROM src_complaint c LEFT JOIN grid_feature f ON f.ID_gid = c.gid WHERE " + " AND ".join(where)
        total = db.read_only("SELECT COUNT(*) AS n " + base, args)
        rows = db.read_only(
            "SELECT " + ", ".join("c." + k for k in COLS) + f", {_GU} AS gu " + base +
            " ORDER BY c.received_date DESC, c.complaint_id LIMIT %s OFFSET %s", [*args, limit, offset])
        return rows, int(total[0]["n"]) if total else 0


_repo: LowComplaintRepository = LowComplaintRepository()


def set_repository(repo: LowComplaintRepository) -> None:
    """시험용: 저장소를 바꿔 끼운다."""
    global _repo
    _repo = repo


def get_repository() -> LowComplaintRepository:
    return _repo
