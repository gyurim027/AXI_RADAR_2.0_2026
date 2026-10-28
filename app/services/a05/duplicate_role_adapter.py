"""A-05 중복 행의 대표·사본 정보를 읽기 전용으로 연결한다."""

import csv
from pathlib import Path

ROLE_FILE = Path(__file__).with_name("duplicate_role_map.csv")


def load_duplicate_roles():
    """검증된 역할 정보 CSV를 읽어 행 식별자별로 정리한다."""
    if not ROLE_FILE.is_file():
        return {}

    with ROLE_FILE.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    roles = {}

    for row in rows:
        key = (row["table_name"], row["row_key"])

        if key in roles:
            raise ValueError(f"Duplicate role key: {key}")

        roles[key] = {
            "duplicate_role": row["duplicate_role"],
            "duplicate_group_id": row["duplicate_group_id"],
            "representative_src_id": row["representative_src_id"],
        }

    return roles


def attach_duplicate_roles(items, roles):
    """원본 응답을 변경하지 않고 A-05 중복 오류에 역할 정보를 붙인다."""
    result = []

    for item in items:
        copied = dict(item)

        if (
            item.get("check_fn") == "A-05"
            and item.get("error_code") == "A05_DUPLICATE_ROW"
        ):
            key = (item.get("table_name"), item.get("row_key"))
            role = roles.get(key)

            copied["duplicate_role"] = (
                role["duplicate_role"] if role else None
            )
            copied["duplicate_group_id"] = (
                role["duplicate_group_id"] if role else None
            )
            copied["representative_src_id"] = (
                role["representative_src_id"] if role else None
            )

        result.append(copied)

    return result
