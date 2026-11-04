"""A-05 DB 중복 검사 결과의 대표·사본 표시용 변환 함수."""

import re

GROUP_PATTERN = re.compile(r"중복 후보 PK:\s*([0-9,\s]+)\.")
ROW_PATTERN = re.compile(r"src_id=(\d+)")


def attach_duplicate_roles(items, roles=None):
    """DB SELECT 결과에 표시 정보만 추가한다. 원본 및 DB 수정 없음."""
    result = []

    for item in items:
        copied = dict(item)

        if (
            item.get("check_fn") == "A-05"
            and item.get("error_code") == "A05_DUPLICATE_ROW"
        ):
            copied["review_classification"] = "pending_review"
            copied["review_label"] = "확인 필요(참고)"
            copied["blocking"] = False

            copied["duplicate_role"] = None
            copied["duplicate_group_id"] = None
            copied["representative_src_id"] = None
            copied["duplicate_role_status"] = "unavailable"

            row_match = ROW_PATTERN.fullmatch(str(item.get("row_key") or ""))
            group_match = GROUP_PATTERN.search(str(item.get("reason") or ""))

            if row_match and group_match and item.get("table_name"):
                members = [
                    int(value.strip())
                    for value in group_match.group(1).split(",")
                ]
                pk = int(row_match.group(1))

                if (
                    len(members) > 1
                    and len(set(members)) == len(members)
                    and pk in members
                ):
                    representative = min(members)
                    table = item["table_name"]

                    copied["duplicate_role"] = (
                        "대표" if pk == representative else "중복 사본"
                    )
                    copied["duplicate_group_id"] = (
                        f"A05_DUP:{table}:{representative}"
                    )
                    copied["representative_src_id"] = str(representative)
                    copied["duplicate_role_status"] = "matched_db_reason"

        result.append(copied)

    return result
