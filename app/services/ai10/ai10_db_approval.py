
"""AI-10 H-07: 운영자 승인 결과를 DB 81 action_template에 저장."""

from app.core import db


def save_approved_template(
    *,
    item_id: str,
    approved_text: str,
    reviewer_id: int,
    approval_note: str,
    evidence_source: str,
    evidence_checked: bool,
    has_findings: bool = False,
    findings_acknowledged: bool = False,
) -> dict:
    """검토 조건을 확인하고 기존 조치 제안 행을 승인 상태로 변경한다."""

    item_id = item_id.strip()
    approved_text = approved_text.strip()
    approval_note = approval_note.strip()
    evidence_source = evidence_source.strip()

    if not item_id or not approved_text:
        raise ValueError("조치 제안 ID와 승인 문장이 필요합니다.")

    if type(reviewer_id) is not int or reviewer_id < 1:
        raise ValueError("유효한 운영자 ID가 필요합니다.")

    if not approval_note:
        raise ValueError("승인 근거가 필요합니다.")

    if not evidence_source or evidence_checked is not True:
        raise ValueError("근거 출처와 운영자 원문 대조 확인이 필요합니다.")

    if has_findings and not findings_acknowledged:
        raise ValueError("검토 표시가 있는 경우 운영자 확인이 필요합니다.")

    # ?? ? ?? ?? ?? ?? ??? ?? DB ??? ????.
    # ???? ??? has_findings ????? ?? ??? ??? ? ??.
    raise ValueError("?? ?? ?? ???: DB ?? ??")

    with db.connect() as con:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT item_id, sentence_review_status
                FROM action_template
                WHERE item_id = %s
                FOR UPDATE
                """,
                (item_id,),
            )
            row = cur.fetchone()

            if row is None:
                raise ValueError(f"존재하지 않는 조치 제안 ID: {item_id}")

            if row["sentence_review_status"] not in (None, "초안"):
                raise ValueError(
                    "현재 상태에서는 승인할 수 없습니다: "
                    + str(row["sentence_review_status"])
                )

            cur.execute(
                """
                UPDATE action_template
                SET action_sentence = %s,
                    sentence_review_status = %s,
                    reviewer = %s,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE item_id = %s
                """,
                (
                    approved_text,
                    "검토 완료",
                    reviewer_id,
                    item_id,
                ),
            )

            if cur.rowcount != 1:
                raise RuntimeError("승인 결과 저장 건수가 올바르지 않습니다.")

            con.commit()

    return {
        "item_id": item_id,
        "sentence_review_status": "검토 완료",
        "reviewer": reviewer_id,
        "db_saved": True,
    }

def get_approved_template(item_id: str) -> dict | None:
    """DB 81번에서 운영자가 승인한 문장만 조회한다."""

    item_id = item_id.strip()
    if not item_id:
        raise ValueError("조치 제안 ID가 필요합니다.")

    rows = db.read_only(
        """
        SELECT
            item_id,
            action_sentence,
            sentence_review_status,
            reviewer,
            reviewed_at
        FROM action_template
        WHERE item_id = %s
          AND sentence_review_status = %s
          AND action_sentence IS NOT NULL
          AND TRIM(action_sentence) <> ''
        """,
        (item_id, "검토 완료"),
    )

    if not rows:
        return None

    row = rows[0]
    return {
        "item_id": row["item_id"],
        "template": row["action_sentence"],
        "reviewer": row["reviewer"],
        "approved_at": (
            row["reviewed_at"].isoformat()
            if row["reviewed_at"] is not None
            else None
        ),
    }