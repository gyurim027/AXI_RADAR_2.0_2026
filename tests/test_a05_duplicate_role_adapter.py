from app.services.a05.duplicate_role_adapter import attach_duplicate_roles


def make_issue(pk, reason):
    return {
        "check_fn": "A-05",
        "error_code": "A05_DUPLICATE_ROW",
        "table_name": "src_lux_point",
        "row_key": f"src_id={pk}",
        "reason": reason,
    }


def test_representative_and_copy():
    reason = "PK 제외 전체 컬럼 동일. 중복 후보 PK: 436, 438. 원본 반복 측정 여부 확인 필요"
    rows = [make_issue(436, reason), make_issue(438, reason)]

    result = attach_duplicate_roles(rows)

    assert result[0]["duplicate_role"] == "대표"
    assert result[1]["duplicate_role"] == "중복 사본"
    assert all(
        item["representative_src_id"] == "436"
        for item in result
    )
    assert all(
        item["duplicate_group_id"] == "A05_DUP:src_lux_point:436"
        for item in result
    )
    assert all(
        item["review_label"] == "확인 필요(참고)"
        and item["blocking"] is False
        for item in result
    )
    assert all(
        item["duplicate_role_status"] == "matched_db_reason"
        for item in result
    )


def test_invalid_reason_does_not_guess():
    row = make_issue(436, "중복 정보 확인 불가")

    result = attach_duplicate_roles([row])[0]

    assert result["duplicate_role"] is None
    assert result["duplicate_role_status"] == "unavailable"


def test_other_function_unchanged():
    row = {
        "check_fn": "A-06",
        "error_code": "A06_TEST",
        "row_key": "id=1",
        "reason": "테스트",
    }

    result = attach_duplicate_roles([row])[0]

    assert result == row


def test_original_not_modified():
    reason = "중복 후보 PK: 436, 438."
    row = make_issue(436, reason)
    original = dict(row)

    attach_duplicate_roles([row])

    assert row == original
