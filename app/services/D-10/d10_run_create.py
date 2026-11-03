
"""D-10: 77 priority_run 회차 생성 서비스 (명시적 run_id 정책).

공용 DB v2.3에서는 run_id가 AUTO_INCREMENT가 아니다.
회차 번호 발급 정책과 산정 기능 연동이 확정되기 전에는
create_run()을 운영 API에 연결하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core import db


class D10RunError(ValueError):
    """회차 생성 입력 또는 참조 조건이 맞지 않음."""


@dataclass(frozen=True)
class RunCreateInput:
    run_id: int
    build_id: str
    rule_version: str
    period_start: date | None = None
    period_end: date | None = None
    note: str | None = None


def validate_run_input(q: RunCreateInput) -> dict[str, Any]:
    """DB 쓰기 없이 D-10 회차 생성 입력을 검사한다."""
    if type(q.run_id) is not int or q.run_id <= 0:
        raise D10RunError("회차 번호는 사전 발급된 양의 정수여야 합니다.")

    for name, value in (
        ("build_id", q.build_id),
        ("rule_version", q.rule_version),
    ):
        max_length = 128 if name == "rule_version" else 30
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value.strip()) > max_length
        ):
            raise D10RunError(
                f"{name}? 1~{max_length}? ?????? ???."
            )

    for value in (q.period_start, q.period_end):
        if value is not None and (
            not isinstance(value, date)
            or isinstance(value, datetime)
        ):
            raise D10RunError(
                "민원 접수 시작일과 종료일은 날짜 또는 None이어야 합니다."
            )

    if (q.period_start is None) != (q.period_end is None):
        raise D10RunError(
            "민원 접수 시작일과 종료일은 함께 입력하거나 모두 비워야 합니다."
        )

    if q.period_start is not None:
        if q.period_start > q.period_end:
            raise D10RunError(
                "민원 접수 시작일이 종료일보다 늦습니다."
            )
        if q.period_end > date.today():
            raise D10RunError(
                "민원 접수 종료일은 미래 날짜일 수 없습니다."
            )

    if q.note is not None and (
        not isinstance(q.note, str)
        or len(q.note) > 300
    ):
        raise D10RunError(
            "비고는 300자 이하 문자열 또는 None이어야 합니다."
        )

    return {
        "run_id": q.run_id,
        "build_id": q.build_id.strip(),
        "rule_version": q.rule_version.strip(),
        "period_start": q.period_start,
        "period_end": q.period_end,
        "note": q.note,
    }


def create_run(q: RunCreateInput) -> dict[str, Any]:
    """사전 발급된 run_id로 회차를 생성한다.

    실제 DB 쓰기 함수이며 현재 운영 API에는 연결하지 않는다.
    중복 번호는 DB 기본키 제약으로 차단한다.
    """
    row = validate_run_input(q)

    with db.connect() as con:
        with con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO priority_run
                (
                    run_id,
                    build_id,
                    rule_version,
                    created_at,
                    note,
                    period_start,
                    period_end
                )
                VALUES
                (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
                """,
                (
                    row["run_id"],
                    row["build_id"],
                    row["rule_version"],
                    row["note"],
                    row["period_start"],
                    row["period_end"],
                ),
            )

            if cur.rowcount != 1:
                raise RuntimeError(
                    "회차 생성 건수가 1건이 아닙니다."
                )

        con.commit()

    return {**row, "created": True}

RUN_ID_LOCK_NAME = "radar:d10:priority_run:allocate"


def allocate_next_run_id(cur) -> int:
    """잠금을 획득한 연결에서만 다음 회차 번호를 계산한다."""
    cur.execute(
        "SELECT COALESCE(MAX(run_id), 0) + 1 AS next_id "
        "FROM priority_run"
    )
    next_id = cur.fetchone()["next_id"]

    if type(next_id) is not int or next_id <= 0:
        raise D10RunError("유효한 다음 회차 번호를 발급할 수 없습니다.")

    return next_id


def create_run_with_allocated_id(
    *,
    build_id: str,
    rule_version: str,
    period_start: date | None = None,
    period_end: date | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """잠금을 사용해 새 회차 번호를 발급하고 DB77에 저장한다."""
    from pymysql.err import IntegrityError

    with db.connect() as con:
        lock_acquired = False

        try:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT GET_LOCK(%s, 5) AS acquired",
                    (RUN_ID_LOCK_NAME,),
                )
                lock_acquired = cur.fetchone()["acquired"] == 1

                if not lock_acquired:
                    raise D10RunError(
                        "회차 번호 발급 잠금을 획득하지 못했습니다."
                    )

                # 잠금 획득 후 최신 회차 번호를 조회한다.
                con.commit()
                cur.execute("START TRANSACTION")
                run_id = allocate_next_run_id(cur)

                row = validate_run_input(
                    RunCreateInput(
                        run_id=run_id,
                        build_id=build_id,
                        rule_version=rule_version,
                        period_start=period_start,
                        period_end=period_end,
                        note=note,
                    )
                )

                cur.execute(
                    """
                    INSERT INTO priority_run
                    (run_id, build_id, rule_version, created_at,
                     note, period_start, period_end)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP,
                            %s, %s, %s)
                    """,
                    (
                        row["run_id"],
                        row["build_id"],
                        row["rule_version"],
                        row["note"],
                        row["period_start"],
                        row["period_end"],
                    ),
                )

                if cur.rowcount != 1:
                    raise RuntimeError("회차 생성 건수가 1건이 아닙니다.")

            con.commit()
            return {**row, "created": True}

        except IntegrityError as exc:
            con.rollback()
            raise D10RunError(
                "회차 번호가 중복되었습니다. 생성 요청을 다시 확인해야 합니다."
            ) from exc

        except Exception:
            con.rollback()
            raise

        finally:
            if lock_acquired:
                with con.cursor() as cur:
                    cur.execute(
                        "SELECT RELEASE_LOCK(%s) AS released",
                        (RUN_ID_LOCK_NAME,),
                    )


def validate_setting_version_ids(
    weight_setting_version_id: int,
    threshold_setting_version_id: int,
    priority_condition_setting_version_id: int,
) -> tuple[int, int, int]:
    """Validate explicit DB62 setting IDs without accessing or writing DB."""
    ids = (
        weight_setting_version_id,
        threshold_setting_version_id,
        priority_condition_setting_version_id,
    )
    if any(type(value) is not int or value <= 0 for value in ids):
        raise D10RunError("INVALID_SETTING_VERSION_ID")
    if len(set(ids)) != 3:
        raise D10RunError("SETTING_VERSION_IDS_MUST_BE_DISTINCT")
    return ids
