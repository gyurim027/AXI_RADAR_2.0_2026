
"""H-01 점검 요청서 미리보기 (1차 배포용).

- 공식 2회차의 실제 후보 DB 조회
- G-03/G-06 개발용 메모리 기록 조회
- 구 도로관리팀 본인 관할만 허용
- 회차 확정 전 ERR-45 반환
- DB 쓰기 및 자동 발송 없음

주의: 담당 부서 판정, F-06 문장, 근거 3개 연동 전.
운영용 완성 요청서가 아닌 개발용 미리보기.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends

from app.api import g03_decision_api as g03
from app.api import g06_finalize_api as g06
from app.core.auth import allowed_gus, current_user
from app.core.responses import ApiError
from app.services.priority.repository import (
    PriorityRepository,
    get_repository,
)

router = APIRouter(
    prefix="/api/h01",
    tags=["H-01 점검 요청서 미리보기"],
)



# 실제 DB의 점수 기여값을 화면용 한국어 명칭으로 변환
INDICATOR_NAMES = {
    "res_fatal_accident_cnt": "격자 내 사망사고 건수",
    "res_hotspot_cnt": "사고다발지 자료 행 수",
    "res_ped_hotspot_cnt": "보행자 사망·중상 다발지 지점 수",
    "cond_blind_spot_cnt": "우회전 사각지대 수",
    "cond_obstacle_cnt": "보행 장애물 수",
    "cond_pothole_detect_cnt": "포트홀 탐지 건수",
    "cond_delineator_detect_cnt": "파손 시선유도봉 탐지 건수",
    "exp_board_alight_daily_avg": "정류소 일평균 승하차량 합계",
    "vul_zone_total": "보호구역 중첩 수",
}



def extract_evidence(details: dict) -> list[dict]:
    """실제 DB의 점수 기여값 중 상위 3개를 찾는다."""

    contributions = details.get("indicator_contributions")

    if not isinstance(contributions, dict):
        return []

    evidence = []

    for code, raw_value in contributions.items():
        if raw_value is None:
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError, OverflowError):
            continue

        if not __import__("math").isfinite(value):
            continue

        evidence.append({
            "indicator_code": code,
            "indicator_name": INDICATOR_NAMES.get(code, code),
            "score_contribution": round(value, 6),
        })

    evidence.sort(
        key=lambda item: (
            -item["score_contribution"],
            item["indicator_code"]
        )
    )

    return evidence[:3]


def build_request_text(evidence: list[dict]) -> str:
    """찾은 근거를 이용해 점검 요청 문장을 만든다."""

    if not evidence:
        return "점검 근거를 확인할 수 없어 추가 검토가 필요합니다."

    names = [item["indicator_name"] for item in evidence]
    reasons = ", ".join(names)

    return (
        f"해당 구역의 점수 산정에서 {reasons} 관련 지표가 "
        "주요 기여 항목으로 확인되었습니다. "
        "현장 점검 및 필요한 조치 검토를 요청합니다."
    )




@router.get("/runs/{run_id}/preview")
def preview(
    run_id: int,
    user: dict = Depends(current_user),
    repo: PriorityRepository = Depends(get_repository),
):
    # 기존 개발용 저장소 활성화 상태 확인
    g03._guard()
    g06._guard()

    # 규림님 확정 사항: 구 도로관리팀만 접근
    if user.get("role") != "district":
        raise ApiError(
            403, "forbidden",
            "구 도로관리팀만 이용할 수 있습니다",
        )

    # 1차 배포: 공식 2회차만 사용
    if run_id != 2:
        raise ApiError(
            409, "unsupported_run",
            "공식 2회차만 지원합니다",
        )

    if repo.get_run(run_id) is None:
        raise ApiError(
            404, "run_not_found",
            "실행 회차를 찾을 수 없습니다",
        )

    permitted_gus = set(allowed_gus(user))
    if not permitted_gus:
        raise ApiError(
            403, "forbidden_gu",
            "담당 관할 구를 확인할 수 없습니다",
        )

    # G-06 회차 확정 여부와 구별 확정 상태
    with g06._lock:
        round_finalized = g06._store.round_finalized(run_id)
        status_records = g06._store.list_run(run_id)

    # 규림님 요청: 확정 전 ERR-45
    if not round_finalized:
        raise ApiError(
            409,
            "ERR-45",
            "우선 점검 대상을 확정한 뒤 만들 수 있습니다.",
        )

    district_statuses = [
        {
            "gu": gu,
            "done": record is not None,
        }
        for gu, record in sorted(status_records.items())
        if gu in permitted_gus
    ]

    # G-03 후보 결정 목록 조회
    with g03._lock:
        decisions = g03._store.list_for_run(run_id)

    groups = defaultdict(list)

    for decision_record in decisions:
        if decision_record.get("decision") != "우선 점검 대상":
            continue

        gid = decision_record.get("gid")
        if not isinstance(gid, str) or not gid:
            continue

        candidate = repo.get_candidate(run_id, gid)
        if candidate is None:
            continue

        gu = candidate.get("gu")

        # 본인 관할 후보만 포함
        if gu not in permitted_gus:
            continue

        department = "담당 부서 확인 필요"

        groups[department].append({
            "gid": gid,
            "gu": gu,
            "score": (
                float(candidate["score"])
                if candidate.get("score") is not None
                else None
            ),
            "rank_no": candidate.get("rank_no"),
            "address": None,
            "landmark": None,
            "data_as_of": None,
            "evidence": extract_evidence(candidate.get("details") or {}),
            "evidence_status": "저장된 실제 점수 기여값 기준",
            "stored_details": candidate.get("details"),
            "request_text": build_request_text(
            extract_evidence(candidate.get("details") or {})
        ),
            "request_text_source": "H01_STORED_SCORE_TEMPLATE",
        })

        result_groups = [
        {
            "department": department,
            "candidates": sorted(
                items, key=lambda x: x["gid"]
            ),
        }
        for department, items in sorted(groups.items())
    ]

    return {
        "run_id": run_id,
        "round_finalized": True,
        "district_confirmations": district_statuses,
        "candidate_count": sum(
            len(group["candidates"])
            for group in result_groups
        ),
        "groups": result_groups,
        "preview_only": True,
        "storage": "development_memory_only",
        "operational_saved": False,
        "automatic_send": False,
        "ready_for_official_export": False,
        "limitations": [
            "G-03/G-06 개발용 메모리 기록 사용",
            "담당 부서 판정 연동 전",
            "실제 근거 3개 및 자료 기준일 연동 전",
            "F-06 요청 문장 연동 전",
        ],
    }
