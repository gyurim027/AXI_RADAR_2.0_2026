"""C-08 표본 선정과 정확도 계산 규칙. DB 행은 이 모듈에 원문 없이 전달한다."""
from __future__ import annotations

from hashlib import sha1

LIMITS = {"AI 판단": 15, "불명": 5, "규칙 판단": 5}
def sample_group(row: dict) -> str | None:
    """검수 전 분류 값으로 층을 정한다. 선정 후에는 DB 스냅샷의 층을 쓴다."""
    method = row.get("class_method")
    if method not in ("AI", "규칙"):
        return None  # 사람 수정값·출처 미상은 시스템 분류 정확도에서 제외
    relevance = row.get("relevance")
    if relevance == "불명":
        return "불명"
    if relevance not in ("보행안전 관련", "비관련"):
        return None
    if method == "AI":
        return "AI 판단"
    if method == "규칙":
        return "규칙 판단"
    return None


def choose_samples(rows: list[dict], run_id: int) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """회차 기간·구로 이미 제한한 행 중 층별 표본과 당시 모집단 건수를 반환한다."""
    groups: dict[str, list[dict]] = {name: [] for name in LIMITS}
    for row in rows:
        group = sample_group(row)
        if group:
            groups[group].append(row)
    counts = {name: len(items) for name, items in groups.items()}
    picked = {}
    for name, items in groups.items():
        picked[name] = sorted(
            items,
            key=lambda row: (sha1(f"{row['complaint_id']}:{run_id}".encode()).hexdigest(),
                             row["complaint_id"]),
        )[:LIMITS[name]]
    return picked, counts


def accuracy(strata: list[dict]) -> dict:
    """층별 정확도와 원래 모집단 크기로 가중한 전체 정확도. 미확인 층은 0%로 간주하지 않는다."""
    detail = []
    weighted = 0.0
    population = 0
    any_pending = False
    any_unfinished = False
    for row in strata:
        n = int(row["population_count"])
        checked = int(row.get("checked_count") or 0)
        correct = int(row.get("correct_count") or 0)
        selected = int(row.get("selected_count") or 0)
        rate = correct / checked if checked else None
        detail.append({"gu": row["gu"], "sample_group": row["sample_group"],
                       "population_count": n, "selected_count": selected, "checked_count": checked,
                       "correct_count": correct, "accuracy": rate})
        if n:
            population += n
            if rate is None:
                any_pending = True
            else:
                weighted += n * rate
            if checked < selected:
                any_unfinished = True
    status = "no_data" if not population else "pending" if any_pending else "partial" if any_unfinished else "complete"
    return {"status": status, "accuracy": weighted / population if status in ("partial", "complete") else None,
            "population_count": population, "strata": detail}
