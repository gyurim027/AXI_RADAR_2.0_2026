"""시험용 계정 6개를 60 app_user에 넣는다 (I-01). 화면 목업 계정과 같은 아이디.

실행 (저장소 루트, PowerShell)
    $env:RADAR_SEED_PASSWORD = "<시험용 비밀번호>"       # 이 창에서만 쓰는 값. 저장소·채팅에 적지 않음
    uv run python -m scripts.auth_create_test_users          # 먼저 무엇을 넣을지만 보여 줌 (DB 안 바꿈)
    uv run python -m scripts.auth_create_test_users --apply  # 실제로 넣기

- 이미 있는 아이디는 건너뛴다. 비밀번호는 해시만 저장한다.
- 역할을 처음 준 것도 61 role_change_log에 한 줄씩 남긴다 (old_role 비움, 고시 제5조③).
- 시험용이다. 시연 뒤 실제 계정은 RADAR 운영자가 따로 만든다.
"""
from __future__ import annotations

import argparse
import os
import sys

from app.core import db
from app.core.auth import hash_password

TEST_USERS = [
    # login_id, display_name, org_name, team_name, gu_name, role
    ("suj", "수정구 담당(시험)", "수정구청", "건설과 도로관리팀", "수정구", "구 도로관리팀"),
    ("jungwon", "중원구 담당(시험)", "중원구청", "건설과 도로관리팀", "중원구", "구 도로관리팀"),
    ("bundang", "분당구 담당(시험)", "분당구청", "건설과 도로관리팀", "분당구", "구 도로관리팀"),
    ("bundang-sidewalk", "분당구 보도 담당(시험)", "분당구청", "건설과 보도관리팀", "분당구", "구 도로관리팀"),
    ("city", "시 도로과 담당(시험)", "성남시", "도로과 도로관리팀", None, "시 도로과"),
    ("operator", "RADAR 운영자(시험)", "RADAR", "운영팀", None, "RADAR 운영자"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 DB에 넣기 (없으면 미리 보기만)")
    args = ap.parse_args()

    password = os.environ.get("RADAR_SEED_PASSWORD", "")
    if len(password) < 8:
        print("RADAR_SEED_PASSWORD(8자 이상)를 먼저 넣어 주세요.")
        return 1

    existing = {r["login_id"] for r in db.read_only("SELECT login_id FROM app_user")}
    todo = [u for u in TEST_USERS if u[0] not in existing]
    for u in TEST_USERS:
        print(("건너뜀(이미 있음) " if u[0] in existing else "넣을 계정 ") + f"{u[0]} · {u[5]} · {u[4] or '3개 구'}")
    if not args.apply or not todo:
        print("미리 보기만 했습니다." if not args.apply else "넣을 계정이 없습니다.")
        return 0

    with db.connect() as con:
        with con.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(user_id), 0) AS m FROM app_user")
            next_id = int(cur.fetchone()["m"]) + 1
            cur.execute("SELECT COALESCE(MAX(role_change_id), 0) AS m FROM role_change_log")
            next_log = int(cur.fetchone()["m"]) + 1
            for login_id, name, org, team, gu, role in todo:
                cur.execute(
                    "INSERT INTO app_user (user_id, login_id, password_hash, display_name, org_name, team_name, "
                    "gu_name, role, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Y', NOW())",
                    (next_id, login_id, hash_password(password), name, org, team, gu, role))
                cur.execute(
                    "INSERT INTO role_change_log (role_change_id, target_user_id, changed_by, old_role, new_role, "
                    "old_gu_name, new_gu_name, changed_at, reason) VALUES (%s, %s, NULL, NULL, %s, NULL, %s, NOW(), %s)",
                    (next_log, next_id, role, gu, "시험 계정 만들기"))
                next_id += 1
                next_log += 1
        con.commit()
    print(f"{len(todo)}개 넣었습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
