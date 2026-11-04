
import json
import sys

import pytest

from app.core import job_run, mailer
from scripts import run_official_priority as command


class MemoryStore:
    def __init__(self, run_id=501):
        self.run_id = run_id
        self.started = []
        self.finished = []
        self.status = "RUNNING"
        self.ref_table = None
        self.ref_id = None
        self.fail_finish = False

    def start(self, *args):
        self.started.append(args)
        return self.run_id

    def finish(self, *args):
        if self.fail_finish:
            raise RuntimeError("SIMULATED_FINISH_DB_FAILURE")
        self.finished.append(args)
        self.status = args[1]
        self.ref_table = args[-2]
        self.ref_id = args[-1]

    def log(self, *args):
        pass

    def alert_failure(self, *args):
        pass


def prepare(tmp_path, monkeypatch, store, run_function):
    export = tmp_path / "reviewed.json"
    export.write_text(
        json.dumps([{"received_date": "2021-01-01","complaint_id":"MOCK_C1","gid":"g1","relevance":"N","class_method":"AI"}]),
        encoding="utf-8",
    )

    monkeypatch.setenv("RADAR_PRIORITY_SETTING_LINKS", "v24")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(job_run, "_store", store)
    monkeypatch.setattr(mailer, "notify_failure", lambda *a, **kw: None)

    def fake_read(sql, params=None):
        if "FROM src_complaint" in sql:return [{"complaint_id":"MOCK_C1","gid":"g1"}]
        if "COUNT(*)" in sql:
            return [{"n": 1}]
        if "FROM job_run WHERE job_run_id=" in sql:
            return [{
                "status": store.status,
                "ref_table": store.ref_table,
                "ref_id": store.ref_id,
            }]
        return [{"ID_gid": "g1"}]

    monkeypatch.setattr(command.db, "read_only", fake_read)
    # Job lifecycle tests isolate DB85 accounting from the independently tested
    # fail-closed replay receipt implementation. Still require its invocation.
    def accepted_replay_receipt(job_id, args, read_only):
        assert job_id == store.run_id
        assert args.existing_run_id == 88
        assert read_only is fake_read
    monkeypatch.setattr(command, "save_replay_receipt", accepted_replay_receipt)
    monkeypatch.setattr(command, "run_from_live_rows", run_function)
    monkeypatch.setattr(sys, "argv", [
        "run_official_priority",
        "--existing-run-id", "88",
        "--weight-setting-id", "2",
        "--threshold-setting-id", "3",
        "--priority-condition-setting-id", "4",
        "--setting-id", "2",
        "--policy-dir", str(tmp_path),
        "--reviewed-json", str(export),
        "--start", "2021-01-01",
        "--end", "2021-01-31",
        "--build-id", "verified-build",
        "--authorized-by", "test-operator",
        "--approval-reference", "test-approval",
        "--commit-official",
    ])


def written_result():
    return {
        "run_id": 88,
        "candidate_count": 1,
        "evidence_count": 1,
        "fingerprint": "test-fingerprint",
        "status": "WRITTEN",
    }


def test_success_links_85_to_77(tmp_path, monkeypatch):
    store = MemoryStore()
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return written_result()

    prepare(tmp_path, monkeypatch, store, run)
    command.main()

    assert len(calls) == 1
    assert calls[0]["explicit_db_write_approval"] is True
    assert store.started[0][2] == "ENGINE"
    assert len(store.finished) == 1
    assert store.finished[0][1] == job_run.SUCCESS
    assert store.finished[0][2] == 1
    assert store.finished[0][-2:] == ("priority_run", "88")


def test_replay_receipt_rejection_blocks_scoring(tmp_path, monkeypatch):
    store = MemoryStore()
    scoring_calls = []
    prepare(tmp_path, monkeypatch, store, lambda **kwargs: scoring_calls.append(kwargs))
    def reject_receipt(job_id, args, read_only):
        raise ValueError("CANDIDATE_ALREADY_STORED_DO_NOT_RERUN")
    monkeypatch.setattr(command, "save_replay_receipt", reject_receipt)
    with pytest.raises(ValueError, match="CANDIDATE_ALREADY_STORED_DO_NOT_RERUN"):
        command.main()
    assert scoring_calls == []
    assert len(store.finished) == 1
    assert store.finished[0][1] == job_run.FAILURE

def test_failed_job_creation_blocks_scoring(tmp_path, monkeypatch):
    store = MemoryStore(run_id=None)
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return written_result()

    prepare(tmp_path, monkeypatch, store, run)

    with pytest.raises(RuntimeError, match="OFFICIAL_JOB_RECORD_UNAVAILABLE"):
        command.main()

    assert calls == []


def test_scoring_failure_is_recorded(tmp_path, monkeypatch):
    store = MemoryStore()

    def run(**kwargs):
        raise ValueError("SIMULATED_SCORING_FAILURE")

    prepare(tmp_path, monkeypatch, store, run)

    with pytest.raises(ValueError, match="SIMULATED_SCORING_FAILURE"):
        command.main()

    assert len(store.finished) == 1
    assert store.finished[0][1] == job_run.FAILURE


@pytest.mark.parametrize("result", [
    {"candidate_count": 1, "status": "WRITTEN"},
    {"run_id": 88, "candidate_count": 1, "status": "BLOCKED"},
])
def test_invalid_write_result_is_rejected(tmp_path, monkeypatch, result):
    store = MemoryStore()
    prepare(tmp_path, monkeypatch, store, lambda **kwargs: result)

    with pytest.raises(RuntimeError, match="OFFICIAL_WRITE_RESULT_INVALID"):
        command.main()

    assert store.finished[0][1] == job_run.FAILURE


def test_finish_failure_does_not_report_success(tmp_path, monkeypatch):
    store = MemoryStore()
    store.fail_finish = True
    prepare(tmp_path, monkeypatch, store, lambda **kw: written_result())

    with pytest.raises(RuntimeError, match="DO_NOT_RERUN"):
        command.main()


def test_wrong_run_reference_blocks_success(tmp_path, monkeypatch):
    store = MemoryStore()
    prepare(tmp_path, monkeypatch, store, lambda **kw: written_result())

    real_finish = store.finish

    def wrong_finish(*args):
        real_finish(*args)
        store.ref_id = "999"

    store.finish = wrong_finish

    with pytest.raises(RuntimeError, match="JOB_NOT_FINALIZED_DO_NOT_RERUN"):
        command.main()
