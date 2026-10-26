"""C-08 저장소. 회차 기간은 77, 선정·검수 기록은 단일 complaint_review 표에 둔다."""
from __future__ import annotations

from decimal import Decimal

from app.core import db
from app.core.auth import GU_LIST
from app.core.responses import ApiError
from app.services.c08.policy import LIMITS, PED_TYPES, TYPE_LIMITS, choose_samples, sample_group, type_group

ADMIN = "전체 분류"
DISTRICT = "유형"
# 범위별: 77의 완료 시각 칸, 층별 표본 수, 층 정하는 규칙
SCOPES = {ADMIN: ("admin_sampled_at", LIMITS, sample_group), DISTRICT: ("district_sampled_at", TYPE_LIMITS, type_group)}


class C08Repository:
    def run_scope(self, run_id: int) -> dict | None:
        rows = db.read_only(
            "SELECT run_id, period_start, period_end, admin_sampled_at, district_sampled_at "
            "FROM priority_run WHERE run_id = %s", (run_id,))
        return rows[0] if rows else None

    def has_complaints(self, run_id: int, gu: str | None = None) -> bool:
        # ensure_admin_samples() 뒤에 호출한다. 새 업로드가 와도 고정된 대상 여부를 보여 준다.
        sql = "SELECT 1 AS hit FROM complaint_review WHERE run_id = %s AND review_scope = %s"
        args: list = [run_id, ADMIN]
        if gu:
            sql += " AND gu = %s"
            args.append(gu)
        return bool(db.read_only(sql + " LIMIT 1", args))

    def type_options(self) -> list[str]:
        return list(PED_TYPES)

    def ensure_admin_samples(self, run_id: int) -> None:
        self._ensure_samples(run_id, ADMIN)

    def ensure_district_samples(self, run_id: int) -> None:
        """구 유형 표본. 운영자 표본을 먼저 고정하고, 운영자 표본에 든 민원은 뽑지 않는다(한 민원을 두 화면에서 고치지 않게)."""
        self._ensure_samples(run_id, ADMIN)
        self._ensure_samples(run_id, DISTRICT)

    def _ensure_samples(self, run_id: int, scope: str) -> None:
        """첫 조회 때 전체 구를 한 거래에서 뽑는다. 0건이어도 완료 시각을 남긴다."""
        mark, limits, group_of = SCOPES[scope]
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(f"SELECT period_start, period_end, {mark} FROM priority_run "
                            "WHERE run_id = %s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if not run or not run["period_start"] or not run["period_end"]:
                    raise ApiError(503, "run_scope_missing", "회차의 민원 자료 기간이 아직 정해지지 않았습니다")
                if run[mark] is not None:
                    return
                if run["period_start"] > run["period_end"]:
                    raise ApiError(503, "invalid_run_period", "회차의 민원 자료 기간이 잘못되었습니다")
                marks = ", ".join(["%s"] * len(GU_LIST))
                cur.execute(
                    "SELECT complaint_id, gu, received_date, masked_summary, relevance, ped_type, "
                    "class_method, class_confidence, class_reason, report_type_raw FROM src_complaint "
                    "WHERE received_date BETWEEN %s AND %s AND gu IN (" + marks + ") "
                    "AND masked_summary IS NOT NULL AND TRIM(masked_summary) <> '' "
                    "AND relevance IN ('보행안전 관련', '비관련', '불명') "
                    "AND class_method IN ('AI', '규칙')",
                    (run["period_start"], run["period_end"], *GU_LIST),
                )
                buckets = {gu: [] for gu in GU_LIST}
                for row in cur.fetchall():
                    buckets[row["gu"]].append(row)
                skip = frozenset()
                if scope == DISTRICT:
                    cur.execute("SELECT complaint_id FROM complaint_review WHERE run_id = %s AND review_scope = %s",
                                (run_id, ADMIN))
                    skip = frozenset(r["complaint_id"] for r in cur.fetchall())
                for gu in GU_LIST:
                    picked, counts = choose_samples(buckets[gu], run_id, limits, group_of, skip)
                    for group in limits:
                        for item in picked[group]:
                            cur.execute(
                                "INSERT INTO complaint_review "
                                "(run_id, complaint_id, gu, review_scope, sample_group, population_count, "
                                "sample_received_date, sample_masked_summary, sample_relevance, sample_ped_type, "
                                "sample_class_method, sample_class_confidence, sample_class_reason) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                (run_id, item["complaint_id"], gu, scope, group, counts[group],
                                 item["received_date"], item["masked_summary"], item["relevance"],
                                 item["ped_type"], item["class_method"], item["class_confidence"],
                                 item["class_reason"]),
                            )
                cur.execute(f"UPDATE priority_run SET {mark} = NOW() WHERE run_id = %s", (run_id,))
            con.commit()

    def samples(self, run_id: int, scope: str, gu: str | None) -> list[dict]:
        sql = (
            "SELECT sample_id, complaint_id, run_id, gu, review_scope, sample_group, "
            "sample_masked_summary AS masked_summary, sample_relevance AS relevance, "
            "sample_ped_type AS ped_type, sample_class_reason AS class_reason, "
            "sample_class_confidence AS class_confidence, result AS done_result, "
            "after_ped_type AS done_label FROM complaint_review "
            "WHERE run_id = %s AND review_scope = %s"
        )
        args: list = [run_id, scope]
        if gu:
            sql += " AND gu = %s"
            args.append(gu)
        sql += " ORDER BY gu, FIELD(sample_group, 'AI 판단', '불명', '규칙 판단'), sample_id"
        return db.read_only(sql, args)

    def review(self, sample_id: int, user: dict, result: str, relevance: str | None,
               ped_type: str | None, ip: str | None) -> None:
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT s.sample_id, s.complaint_id, s.gu, s.review_scope, s.result, "
                    "s.sample_received_date, s.sample_masked_summary, s.sample_relevance, "
                    "s.sample_ped_type, s.sample_class_method, s.sample_class_confidence, "
                    "s.sample_class_reason, c.gu AS current_gu, c.received_date, "
                    "c.masked_summary, c.relevance, c.ped_type, c.class_method, "
                    "c.class_confidence, c.class_reason "
                    "FROM complaint_review s JOIN src_complaint c ON c.complaint_id = s.complaint_id "
                    "WHERE s.sample_id = %s FOR UPDATE", (sample_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ApiError(404, "sample_not_found", "표본을 찾을 수 없습니다")
                if row["result"] is not None:
                    raise ApiError(409, "already_reviewed", "이미 확인한 표본입니다")
                if user["role"] == "district":
                    if row["review_scope"] != DISTRICT or row["gu"] != user.get("gu"):
                        raise ApiError(403, "forbidden_sample", "담당 구의 유형 표본만 확인할 수 있습니다")
                    if relevance is not None:
                        raise ApiError(403, "relevance_forbidden", "구 도로관리팀은 관련 여부를 고칠 수 없습니다")
                    if not self.type_options():
                        raise ApiError(409, "types_pending", "유형 목록이 아직 정해지지 않았습니다")
                elif row["review_scope"] != ADMIN:
                    raise ApiError(403, "forbidden_sample", "운영자 표본이 아닙니다")

                fields = ("masked_summary", "relevance", "ped_type", "class_method", "class_reason")
                changed = (row["gu"] != row["current_gu"] or
                           row["sample_received_date"] != row["received_date"] or
                           any(row[f"sample_{field}"] != row[field] for field in fields))
                left, right = row["sample_class_confidence"], row["class_confidence"]
                if left is not None and right is not None:
                    changed = changed or Decimal(str(left)) != Decimal(str(right))
                else:
                    changed = changed or left != right
                if changed:
                    raise ApiError(409, "sample_changed", "표본 선정 뒤 분류 내용이 바뀌었습니다")

                before_rel, before_type = row["sample_relevance"], row["sample_ped_type"]
                after_rel = relevance if relevance is not None else before_rel
                after_type = ped_type if ped_type is not None else before_type
                if result == "맞음":
                    if relevance is not None or ped_type is not None:
                        raise ApiError(422, "unexpected_change", "맞음에는 고칠 값을 넣지 않습니다")
                else:
                    if after_rel == before_rel and after_type == before_type:
                        raise ApiError(422, "unchanged_review", "고침에는 바뀐 값을 넣어 주세요")
                    if ped_type is not None and ped_type != before_type and ped_type not in self.type_options():
                        raise ApiError(422, "invalid_type", "유형 목록에 없는 값입니다")
                    if after_rel != "보행안전 관련":
                        after_type = None

                cur.execute(
                    "UPDATE complaint_review SET result = %s, after_relevance = %s, after_ped_type = %s, "
                    "reviewed_by = %s, reviewed_at = NOW() WHERE sample_id = %s AND result IS NULL",
                    (result, after_rel, after_type, user["user_id"], sample_id),
                )
                if result == "고침":
                    # class_method는 관련 여부 판단 방법이다. 유형만 고치면 보존한다.
                    after_method = "사람" if after_rel != before_rel else row["class_method"]
                    changes = [("relevance", before_rel, after_rel), ("ped_type", before_type, after_type),
                               ("class_method", row["class_method"], after_method)]
                    for column, old, new in changes:
                        if old != new:
                            cur.execute(
                                "INSERT INTO src_complaint_change "
                                "(complaint_id, changed_column, old_value, new_value, load_batch, "
                                "changed_by_type, changed_by_user) VALUES (%s, %s, %s, %s, NULL, '사람', %s)",
                                (row["complaint_id"], column, old, new, user["user_id"]),
                            )
                    cur.execute("UPDATE src_complaint SET relevance = %s, ped_type = %s, class_method = %s, "
                                "db_last_updated_at = NOW() WHERE complaint_id = %s",
                                (after_rel, after_type, after_method, row["complaint_id"]))
                cur.execute("INSERT INTO access_audit "
                            "(actor_ref, resource_kind, resource_key, client_ip, access_reason) "
                            "VALUES (%s, '분류 확인', %s, %s, '분류 검수')",
                            (user["user_id"], row["gu"], ip))
            con.commit()

    def accuracy_strata(self, run_id: int, review_scope: str) -> list[dict]:
        if review_scope not in (ADMIN, DISTRICT):
            raise ValueError("모르는 검수 범위")
        correct_field = ("sample_relevance <=> after_relevance" if review_scope == ADMIN
                         else "sample_ped_type <=> after_ped_type")
        sql = (
            "SELECT gu, sample_group, MIN(population_count) AS population_count, "
            "MAX(population_count) AS population_max, COUNT(*) AS selected_count, "
            "SUM(result IS NOT NULL) AS checked_count, "
            "SUM(result IS NOT NULL AND " + correct_field + ") AS correct_count "
            "FROM complaint_review WHERE run_id = %s AND review_scope = %s "
            "GROUP BY gu, sample_group "
            "ORDER BY gu, FIELD(sample_group, 'AI 판단', '불명', '규칙 판단')"
        )
        rows = db.read_only(sql, (run_id, review_scope))
        if any(int(r["population_count"]) != int(r["population_max"]) for r in rows):
            raise ApiError(503, "population_snapshot_inconsistent", "표본 모집단 기록이 일치하지 않습니다")
        return rows

    def evaluation_rows(self, run_id: int, target: str) -> list[dict]:
        sql = (
            "SELECT sample_id, review_scope, sample_group, "
            "sample_masked_summary AS masked_summary, after_relevance, after_ped_type "
            "FROM complaint_review WHERE run_id = %s AND result IS NOT NULL "
            "AND sample_masked_summary <> ''"
        )
        args: list = [run_id]
        if target == "relevance":
            sql += " AND review_scope = %s AND after_relevance IS NOT NULL"
            args.append(ADMIN)
        else:
            sql += " AND review_scope = %s AND after_relevance = '보행안전 관련' "
            sql += "AND after_ped_type IS NOT NULL"
            args.append(DISTRICT)
        sql += " ORDER BY sample_id"
        return db.read_only(sql, args)


_repository = C08Repository()


def get_repository() -> C08Repository:
    return _repository
