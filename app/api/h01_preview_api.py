
"""H-01 점검 요청서 미리보기 (1차 시연용).

- 공식 4회차의 실제 후보 DB 조회
- G-03/G-06 개발용 메모리 기록 조회
- 구 도로관리팀의 본인 관할만 허용
- 회차 확정 전 ERR-45 반환
- 실제 점수 기여값 상위 3개 표시
- 담당 부서 미확정 상태 표시
- 참고 주소 및 참고 시설 표시 정책 적용
- DB 쓰기 및 자동 발송 없음

주의:
G-03/G-06 확정은 개발용 메모리 상태이며 공식 운영 확정이 아니다.
F-06 실제 데이터용 생성 기능은 아직 연동하지 않았다.
자료 기준일은 확인 전까지 None으로 반환한다.
"""

from collections import defaultdict
from math import isfinite

from fastapi import APIRouter, Depends

from app.api import g03_decision_api as g03
from app.api import g06_finalize_api as g06
from app.core.auth import allowed_gus, current_user
from app.core.responses import ApiError
from app.services.priority.department_resolution import unresolved_department
from app.services.priority.repository import (
    PriorityRepository,
    get_repository,
)


router = APIRouter(
    prefix="/api/h01",
    tags=["H-01 점검 요청서 미리보기"],
)


# 실제 DB의 점수 기여값을 화면용 한국어 이름으로 변환
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
    """실제 DB의 점수 기여값에서 상위 3개를 추출한다."""

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

        if not isfinite(value):
            continue

        evidence.append({
            "indicator_code": code,
            "indicator_name": INDICATOR_NAMES.get(code, code),
            "score_contribution": round(value, 6),
        })

    evidence.sort(
        key=lambda item: (
            -item["score_contribution"],
            item["indicator_code"],
        )
    )

    return evidence[:3]


def build_request_text(evidence: list[dict]) -> str:
    """실제 점수 근거를 이용해 점검 요청 문장을 만든다.

    F-06 실제 데이터용 연동 전까지 사용하는 H-01 자체 템플릿.
    참고 시설의 구체적인 이름과 주소를 문장에 포함하지 않는다.
    """

    if not evidence:
        return "점검 근거를 확인할 수 없어 추가 검토가 필요합니다."

    names = [item["indicator_name"] for item in evidence]
    reasons = ", ".join(names)

    return (
        f"해당 구역의 점수 산정에서 {reasons} 관련 지표가 "
        "주요 기여 항목으로 확인되었습니다. "
        "현장 점검 및 필요한 조치 검토를 요청합니다."
    )


def safe_landmark(
    landmark: str | None,
    source: str | None,
) -> str | None:
    """격자에 연결된 참고 시설명을 안전한 문구로 바꾼다.

    같은 격자에 연결된 시설이지 위험이 발생한 정확한 장소가 아니다.
    """

    if not landmark:
        return None

    if source == "보호구역 시설":
        return "보호구역 인근"

    if source == "어린이집·유치원":
        return "어린이집·유치원 인근"

    if source == "횡단보도":
        return "횡단보도 인근"

    if source == "안전 CCTV":
        return "CCTV 인근"

    if source == "보안등":
        return "보안등 인근"

    if source == "버스정류소":
        return landmark

    # 출처가 확인되지 않으면 실제 시설명을 표시하지 않는다.
    return None


@router.get("/runs/{run_id}/preview")
def preview(
    run_id: int,
    user: dict = Depends(current_user),
    repo: PriorityRepository = Depends(get_repository),
):
    """구 도로관리팀의 점검 요청서 개발용 미리보기."""

    # 구 도로관리팀만 접근 허용
    if user.get("role") != "district":
        raise ApiError(
            403,
            "forbidden",
            "구 도로관리팀만 이용할 수 있습니다",
        )

    # 1차 시연은 공식 4회차만 지원
    if run_id != 4:
        raise ApiError(
            409,
            "unsupported_run",
            "공식 4회차만 지원합니다",
        )

    # 개발용 저장소 활성화 검사
    g03._guard()
    g06._guard()

    # 실제 회차가 있는지 확인
    if repo.get_run(run_id) is None:
        raise ApiError(
            404,
            "run_not_found",
            "실행 회차를 찾을 수 없습니다",
        )

    # 로그인 사용자의 담당 구 확인
    permitted_gus = set(allowed_gus(user))

    if not permitted_gus:
        raise ApiError(
            403,
            "forbidden_gu",
            "담당 관할 구를 확인할 수 없습니다",
        )

    # G-06 개발용 확정 상태 조회
    with g06._lock:
        round_finalized = g06._store.round_finalized(run_id)
        status_records = g06._store.list_run(run_id)

    # 확정되지 않았으면 요청서 미리보기 차단
    if not round_finalized:
        raise ApiError(
            409,
            "ERR-45",
            "우선 점검 대상을 확정한 뒤 만들 수 있습니다.",
        )

    # 본인 관할 구의 확정 상태만 제공
    district_statuses = [
        {
            "gu": gu,
            "done": record is not None,
        }
        for gu, record in sorted(status_records.items())
        if gu in permitted_gus
    ]

    # G-03 개발용 결정 목록 조회
    with g03._lock:
        decisions = g03._store.list_for_run(run_id)

    # 담당 부서별 그룹 생성
    groups = defaultdict(list)

    for decision_record in decisions:

        # 실제로 우선 점검 대상으로 선택된 후보만 사용
        if decision_record.get("decision") != "우선 점검 대상":
            continue

        gid = decision_record.get("gid")

        if not isinstance(gid, str) or not gid:
            continue

        # 실제 MySQL 후보 조회
        candidate = repo.get_candidate(run_id, gid)

        if candidate is None:
            continue

        gu = candidate.get("gu")

        # 다른 구 후보는 제외
        if gu not in permitted_gus:
            continue

        # 담당 부서 정보 확인
        dept_info = unresolved_department(candidate)

        department = (
            dept_info.get("department")
            if (
                dept_info.get("departmentStatus") != "확인 필요"
                and dept_info.get("department")
            )
            else "담당 부서 확인 필요"
        )

        # 실제 점수 근거 상위 3개
        evidence = extract_evidence(
            candidate.get("details") or {}
        )

        # 대환님 후보 데이터의 출처 정보 사용
        address = candidate.get("address")
        address_source = candidate.get("addressSource")

        landmark_source = candidate.get("landmarkSource")
        landmark = safe_landmark(
            candidate.get("landmark"),
            landmark_source,
        )

        # H-01 점검 요청서 후보 정보
        groups[department].append({
            "gid": gid,
            "gu": gu,
            "score": (
                float(candidate["score"])
                if candidate.get("score") is not None
                else None
            ),
            "rank_no": candidate.get("rank_no"),

            # 주소는 정확한 위험 위치가 아닌 참고 주소
            "address": address,
            "address_source": address_source,

            # 시설명 비노출 정책 적용
            "landmark": landmark,
            "landmark_source": landmark_source,

            "department_status": dept_info.get(
                "departmentStatus"
            ),
            "department_reason": dept_info.get(
                "departmentReason"
            ),

            # 자료 기준일은 확인 전까지 null
            "data_as_of": None,

            "evidence": evidence,
            "evidence_status": "저장된 실제 점수 기여값 기준",



            "request_text": build_request_text(evidence),
            "request_text_source": "H01_STORED_SCORE_TEMPLATE",
        })

    # 담당 부서별로 후보 정리
    result_groups = [
        {
            "department": department,
            "candidates": sorted(
                items,
                key=lambda x: x["gid"],
            ),
        }
        for department, items in sorted(groups.items())
    ]

    # 프론트엔드에 전달할 최종 응답
    return {
        "run_id": run_id,
        "round_finalized": True,
        "district_confirmations": district_statuses,
        "candidate_count": sum(
            len(group["candidates"])
            for group in result_groups
        ),
        "groups": result_groups,

        # 개발용 미리보기 구분
        "preview_only": True,
        "storage": "development_memory_only",
        "operational_saved": False,
        "automatic_send": False,
        "ready_for_official_export": False,

        "limitations": [
            "G-03/G-06 개발용 메모리 기록 사용",
            "담당 부서는 미확정일 수 있음",
            "주소와 대표 지점은 격자 연결 참고 정보",
            "자료 기준일 확인 전",
            "F-06 실제 데이터용 문장 연동 전",
        ],
    }
