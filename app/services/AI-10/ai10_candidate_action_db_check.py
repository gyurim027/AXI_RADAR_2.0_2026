
"""AI-10 후보별 조치 제안 저장 전 DB 참조 검증.

SQL v2.3의 기존 78·81번 테이블을 조회한다.
DB 저장, 승인 상태 변경, AI 모델 호출은 수행하지 않는다.
"""

from typing import Any


class CandidateActionDBCheckError(ValueError):
    """기존 DB의 참조 관계 또는 승인 조건이 충족되지 않은 경우."""


def verify_candidate_action_references(
    cursor: Any,
    *,
    run_id: int,
    gid: str,
    item_id: str,
) -> dict[str, Any]:
    """선정된 후보와 승인 문장 틀이 실제 DB에 존재하는지 확인한다."""

    if type(run_id) is not int or run_id < 1:
        raise CandidateActionDBCheckError("유효한 실행 번호가 필요합니다.")

    if not isinstance(gid, str) or not gid.strip():
        raise CandidateActionDBCheckError("격자 번호가 필요합니다.")

    if not isinstance(item_id, str) or not item_id.strip():
        raise CandidateActionDBCheckError("조치 제안 항목 번호가 필요합니다.")

    gid = gid.strip()
    item_id = item_id.strip()

    cursor.execute(
        """
        SELECT selected_yn
        FROM priority_candidate
        WHERE run_id = %s AND gid = %s
        """,
        (run_id, gid),
    )
    candidate = cursor.fetchone()

    if candidate is None:
        raise CandidateActionDBCheckError(
            "78번 테이블에서 해당 실행 회차와 격자를 찾을 수 없습니다."
        )

    selected_yn = (
        candidate["selected_yn"]
        if isinstance(candidate, dict)
        else candidate[0]
    )

    if selected_yn != "Y":
        raise CandidateActionDBCheckError(
            "선정되지 않은 후보에는 조치 제안을 연결할 수 없습니다."
        )

    cursor.execute(
        """
        SELECT item_id, sentence_review_status, action_sentence
        FROM action_template
        WHERE item_id = %s
        """,
        (item_id,),
    )
    template = cursor.fetchone()

    if template is None:
        raise CandidateActionDBCheckError(
            "81번 테이블에서 해당 조치 제안 문장 틀을 찾을 수 없습니다."
        )

    if isinstance(template, dict):
        db_item_id = template["item_id"]
        status = template["sentence_review_status"]
        sentence = template["action_sentence"]
    else:
        db_item_id, status, sentence = template

    if db_item_id != item_id:
        raise CandidateActionDBCheckError(
            "조회한 조치 제안 항목 번호가 요청값과 다릅니다."
        )

    if status != "검토 완료":
        raise CandidateActionDBCheckError(
            "운영자 검토 완료 상태가 아닌 문장 틀입니다."
        )

    if not isinstance(sentence, str) or not sentence.strip():
        raise CandidateActionDBCheckError(
            "승인된 문장 틀의 내용이 비어 있습니다."
        )

    return {
        "run_id": run_id,
        "gid": gid,
        "item_id": item_id,
        "selected_yn": selected_yn,
        "sentence_review_status": status,
        "reference_verified": True,
    }
