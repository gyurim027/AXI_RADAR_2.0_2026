"""기간 기준 단일 표의 선정 고정·검수 거래를 확인한다. 실제 DB는 사용하지 않는다."""
from contextlib import contextmanager
from datetime import date

import pytest

from app.core import db
from app.core.responses import ApiError
from app.services.c08.repository import C08Repository


class FakeCursor:
    def __init__(self, *, reviewed=False, fail_audit=False, scope="전체 분류", stale=False,
                 candidates=None, marked=False):
        self.reviewed = reviewed
        self.fail_audit = fail_audit
        self.scope = scope
        self.stale = stale
        self.candidates = candidates or []
        self.marked = marked
        self.district_marked = False
        self.admin_ids = []
        self.last_sql = ""
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, args=()):
        self.last_sql = sql
        self.statements.append((sql, args))
        if self.fail_audit and "INSERT INTO access_audit" in sql:
            raise RuntimeError("audit failed")
        if sql.startswith("UPDATE priority_run SET admin_sampled_at"):
            self.marked = True
        if sql.startswith("UPDATE priority_run SET district_sampled_at"):
            self.district_marked = True

    def fetchone(self):
        if "FROM complaint_review s JOIN src_complaint" in self.last_sql:
            return {"sample_id": 11, "complaint_id": "C000000000001", "gu": "수정구",
                    "review_scope": self.scope, "result": "맞음" if self.reviewed else None,
                    "relevance": "보행안전 관련", "ped_type": None,
                    "class_method": "AI", "masked_summary": "가린 요약",
                    "current_gu": "수정구", "received_date": date(2026, 1, 3),
                    "sample_received_date": date(2026, 1, 3),
                    "class_confidence": 0.8, "class_reason": "판단 근거",
                    "sample_relevance": "비관련" if self.stale else "보행안전 관련",
                    "sample_ped_type": None, "sample_class_method": "AI",
                    "sample_masked_summary": "가린 요약", "sample_class_confidence": 0.8,
                    "sample_class_reason": "판단 근거"}
        if "FROM priority_run" in self.last_sql:
            return {"period_start": date(2026, 1, 1), "period_end": date(2026, 1, 31),
                    "admin_sampled_at": date(2026, 1, 31) if self.marked else None,
                    "district_sampled_at": date(2026, 1, 31) if self.district_marked else None}
        return None

    def fetchall(self):
        if "FROM src_complaint" in self.last_sql:
            return self.candidates
        if "SELECT complaint_id FROM complaint_review" in self.last_sql:
            return [{"complaint_id": c} for c in self.admin_ids]
        return []


class FakeConnection:
    def __init__(self, cursor):
        self.cur = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def connection(monkeypatch, **kw):
    con = FakeConnection(FakeCursor(**kw))

    @contextmanager
    def connect():
        try:
            yield con
        except Exception:
            con.rollback()
            raise

    monkeypatch.setattr(db, "connect", connect)
    return con


USER = {"user_id": 9, "role": "operator"}


def test_already_reviewed_is_rejected_before_writes(monkeypatch):
    con = connection(monkeypatch, reviewed=True)
    with pytest.raises(ApiError) as error:
        C08Repository().review(11, USER, "맞음", None, None, "127.0.0.1")
    assert error.value.status == 409
    assert not any(sql.startswith(("UPDATE", "INSERT")) for sql, _ in con.cur.statements)
    assert con.rolled_back and not con.committed


def test_audit_failure_prevents_review_commit(monkeypatch):
    con = connection(monkeypatch, fail_audit=True)
    with pytest.raises(RuntimeError):
        C08Repository().review(11, USER, "고침", "비관련", None, "127.0.0.1")
    assert any("UPDATE complaint_review SET result" in sql for sql, _ in con.cur.statements)
    assert any("INSERT INTO src_complaint_change " in sql for sql, _ in con.cur.statements)
    audit_args = [args for sql, args in con.cur.statements if "INSERT INTO access_audit" in sql][0]
    assert audit_args == (9, "수정구", "127.0.0.1")
    assert con.rolled_back and not con.committed


def test_changed_sample_is_rejected_before_review_write(monkeypatch):
    con = connection(monkeypatch, stale=True)
    with pytest.raises(ApiError) as error:
        C08Repository().review(11, USER, "맞음", None, None, "127.0.0.1")
    assert error.value.status == 409 and error.value.code == "sample_changed"
    assert not any(sql.startswith(("UPDATE", "INSERT")) for sql, _ in con.cur.statements)
    assert con.rolled_back and not con.committed


def test_type_only_change_preserves_relevance_method(monkeypatch):
    con = connection(monkeypatch, scope="유형")

    class WithTypes(C08Repository):
        def type_options(self):
            return ["보행로"]

    WithTypes().review(11, {"user_id": 9, "role": "district", "gu": "수정구"},
                       "고침", None, "보행로", "127.0.0.1")
    updates = [args for sql, args in con.cur.statements if sql.startswith("UPDATE src_complaint")]
    assert updates[0][2] == "AI"
    changed = [args[1] for sql, args in con.cur.statements if sql.startswith("INSERT INTO src_complaint_change")]
    assert changed == ["ped_type"]
    assert con.committed and not con.rolled_back


def test_accuracy_and_evaluation_use_frozen_fields(monkeypatch):
    queries = []
    monkeypatch.setattr(db, "read_only", lambda sql, args: queries.append((sql, args)) or [])
    repo = C08Repository()
    repo.accuracy_strata(7, "전체 분류")
    assert "sample_relevance <=> after_relevance" in queries[-1][0]
    repo.accuracy_strata(7, "유형")
    assert "sample_ped_type <=> after_ped_type" in queries[-1][0]
    repo.evaluation_rows(7, "pedType")
    assert "review_scope = %s" in queries[-1][0]
    assert "sample_masked_summary AS masked_summary" in queries[-1][0]
    assert "JOIN src_complaint" not in queries[-1][0]
    assert queries[-1][1] == [7, "유형"]


def test_empty_period_is_marked_once_and_does_not_acquire_later_rows(monkeypatch):
    con = connection(monkeypatch)
    repo = C08Repository()
    repo.ensure_admin_samples(7)
    assert con.cur.marked and con.committed
    assert not any(sql.startswith("INSERT INTO complaint_review") for sql, _ in con.cur.statements)
    con.cur.candidates = [{"complaint_id": "LATE"}]
    before = len(con.cur.statements)
    repo.ensure_admin_samples(7)
    assert len(con.cur.statements) == before + 1  # 잠근 회차의 완료 표시만 읽음
    assert not any("FROM src_complaint" in sql for sql, _ in con.cur.statements[before:])


def test_period_candidates_save_one_snapshot_per_sample(monkeypatch):
    base = {"gu": "수정구", "received_date": date(2026, 1, 3), "masked_summary": "가린 요약",
            "relevance": "보행안전 관련", "ped_type": None, "class_method": "AI",
            "class_confidence": 0.8, "class_reason": "판단 근거"}
    con = connection(monkeypatch, candidates=[dict(base, complaint_id="A"), dict(base, complaint_id="B"),
                                              dict(base, complaint_id="C", relevance="불명", class_method="사람")])
    C08Repository().ensure_admin_samples(7)
    sample_args = [args for sql, args in con.cur.statements if sql.startswith("INSERT INTO complaint_review")]
    assert len(sample_args) == 2
    assert {args[1] for args in sample_args} == {"A", "B"}
    assert all(args[5] == 2 and args[7] == "가린 요약" for args in sample_args)
    source_sql = next(sql for sql, _ in con.cur.statements if "FROM src_complaint" in sql)
    assert "received_date BETWEEN %s AND %s" in source_sql
    assert "class_method IN ('AI', '규칙')" in source_sql
    assert "complaint_upload_membership" not in source_sql
    assert con.cur.marked and con.committed


def test_population_mismatch_is_rejected(monkeypatch):
    monkeypatch.setattr(db, "read_only", lambda *_: [{"population_count": 2, "population_max": 3}])
    with pytest.raises(ApiError) as error:
        C08Repository().accuracy_strata(7, "전체 분류")
    assert error.value.code == "population_snapshot_inconsistent"


def test_admin_type_change_uses_iss016_list(monkeypatch):
    connection(monkeypatch)
    with pytest.raises(ApiError) as error:
        C08Repository().review(11, {"user_id": 1, "role": "operator"}, "고침", None, "도로 파손", "127.0.0.1")
    assert error.value.status == 422 and error.value.code == "invalid_type"
    con = connection(monkeypatch)
    C08Repository().review(11, {"user_id": 1, "role": "operator"}, "고침", None, "노면", "127.0.0.1")
    changed = [args[1:3] for sql, args in con.cur.statements if sql.startswith("INSERT INTO src_complaint_change")]
    assert changed == [("ped_type", None)]
    assert con.committed


def test_district_samples_are_related_typed_and_skip_admin_samples(monkeypatch):
    base = {"gu": "수정구", "received_date": date(2026, 1, 3), "masked_summary": "가린 요약",
            "relevance": "보행안전 관련", "ped_type": "노면", "class_method": "AI",
            "class_confidence": 0.8, "class_reason": "판단 근거", "report_type_raw": None}
    con = connection(monkeypatch, marked=True, candidates=[
        dict(base, complaint_id="A"), dict(base, complaint_id="B"),
        dict(base, complaint_id="P", ped_type="주정차", report_type_raw="횡단보도 불법 주정차"),
        dict(base, complaint_id="N", relevance="비관련", ped_type=None),
        dict(base, complaint_id="X", ped_type="도로 파손")])
    con.cur.admin_ids = ["B"]
    C08Repository().ensure_district_samples(7)
    sample_args = [args for sql, args in con.cur.statements if sql.startswith("INSERT INTO complaint_review")]
    assert {(args[1], args[3], args[4], args[5]) for args in sample_args} == {
        ("A", "유형", "AI 판단", 2), ("P", "유형", "규칙 판단", 1)}      # B는 운영자 표본이라 빼되 모집단에는 셈
    assert con.cur.district_marked and con.committed
