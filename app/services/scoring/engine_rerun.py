"""Explicit fail-closed replay of a failed ENGINE job.

Only jobs created after this integration with a verified DB85 replay receipt
are eligible. Never re-run legacy round 1, existing round 2, or any round
with stored DB78 candidates. No credential or personal data is persisted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from app.core import rerun

MARKER = "ENGINE_REPLAY_V1:"
REPLAY_DIR = Path("out") / "engine_rerun"


class ReplayBlocked(ValueError):
    pass


def _repo_root() -> Path:
    # app/services/scoring/engine_rerun.py -> repository root
    return Path(__file__).resolve().parents[3]


def _receipt_path(job_id: int) -> Path:
    if type(job_id) is not int or job_id <= 0:
        raise ReplayBlocked("INVALID_JOB_ID")
    return _repo_root() / REPLAY_DIR / f"job_{job_id}.json"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one(read_only, sql: str, args: tuple):
    rows = read_only(sql, args)
    if len(rows) != 1:
        raise ReplayBlocked("REPLAY_IDENTITY_NOT_UNIQUE")
    return rows[0]


def _validate_no_output(run_id: int, read_only) -> None:
    if type(run_id) is not int or run_id <= 2:
        raise ReplayBlocked("LEGACY_OR_OFFICIAL_RUN_PROTECTED")
    row = _one(read_only,
        "SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s", (run_id,))
    if int(row["n"]) != 0:
        raise ReplayBlocked("CANDIDATE_ALREADY_STORED_DO_NOT_RERUN")


def _file_hash(path: str) -> str:
    p = Path(path).resolve(strict=True)
    if not p.is_file():
        raise ReplayBlocked("REVIEWED_SOURCE_NOT_FILE")
    return _digest(p.read_bytes())


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def save_replay_receipt(job_id: int, args, read_only) -> None:
    """Persist only deterministic arguments and bind their digest to DB85.

    Caller must do this before performing any DB77/78 scoring writes.
    Missing DB85 log must abort the original operation, not allow untracked replay.
    """
    from app.core import db
    run_id = int(args.existing_run_id)
    _validate_no_output(run_id, read_only)
    if bool(args.native_full_source) == bool(args.reviewed_json):
        raise ReplayBlocked("EXACTLY_ONE_SOURCE_REQUIRED")
    payload = {
        "version": 1, "original_job_id": job_id, "existing_run_id": run_id,
        "setting_id": int(args.setting_id), "policy_dir": str(Path(args.policy_dir).resolve()),
        "weight_setting_id": int(args.weight_setting_id),
        "threshold_setting_id": int(args.threshold_setting_id),
        "priority_condition_setting_id": int(args.priority_condition_setting_id),
        "native_full_source": bool(args.native_full_source),
        "expected_audit_sha256": args.expected_audit_sha256,
        "reviewed_json": str(Path(args.reviewed_json).resolve()) if args.reviewed_json else None,
        "reviewed_json_sha256": _file_hash(args.reviewed_json) if args.reviewed_json else None,
        "start": str(args.start), "end": str(args.end),
        "build_id": args.build_id, "authorized_by": args.authorized_by,
        "approval_reference": args.approval_reference,
    }
    raw = _canonical(payload)
    path = _receipt_path(job_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Creation is exclusive: a pre-existing file signals a conflict, not an update.
    with path.open("xb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    digest = _digest(raw)
    # This is not JobHandle.log: logging must NOT silently swallow errors.
    from app.core.job_run import get_store
    get_store().log(job_id, MARKER + digest)
    logged = read_only("SELECT COUNT(*) AS n FROM job_run_log "
                       "WHERE job_run_id=%s AND message=%s", (job_id, MARKER + digest))
    if len(logged) != 1 or int(logged[0]["n"]) != 1:
        raise ReplayBlocked("DB85_REPLAY_RECEIPT_NOT_CONFIRMED")


def _load_verified(run: dict, read_only) -> dict:
    if run.get("module") != "ENGINE" or run.get("status") != "실패":
        raise ReplayBlocked("NOT_A_FAILED_ENGINE_JOB")
    if run.get("ref_table") != "priority_run":
        raise ReplayBlocked("REPLAY_RUN_REFERENCE_REQUIRED")
    try:
        run_id = int(run["ref_id"])
        job_id = int(run["job_run_id"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ReplayBlocked("REPLAY_IDENTITY_MISSING") from exc
    _validate_no_output(run_id, read_only)
    raw = _receipt_path(job_id).read_bytes()
    if len(raw) > 8192:
        raise ReplayBlocked("REPLAY_RECEIPT_TOO_LARGE")
    digest = _digest(raw)
    signed = read_only("SELECT COUNT(*) AS n FROM job_run_log "
                       "WHERE job_run_id=%s AND message=%s", (job_id, MARKER + digest))
    if len(signed) != 1 or int(signed[0]["n"]) != 1:
        raise ReplayBlocked("REPLAY_RECEIPT_SHA_MISMATCH")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("version") != 1 or payload.get("original_job_id") != job_id or payload.get("existing_run_id") != run_id:
        raise ReplayBlocked("REPLAY_RECEIPT_IDENTITY_MISMATCH")
    expected_keys = {"version", "original_job_id", "existing_run_id", "setting_id",
      "policy_dir", "weight_setting_id", "threshold_setting_id", "priority_condition_setting_id",
      "native_full_source", "expected_audit_sha256", "reviewed_json", "reviewed_json_sha256",
      "start", "end", "build_id", "authorized_by", "approval_reference"}
    if set(payload) != expected_keys:
        raise ReplayBlocked("REPLAY_RECEIPT_KEYS_MISMATCH")
    if payload["native_full_source"]:
        if not payload["expected_audit_sha256"] or payload["reviewed_json"] is not None:
            raise ReplayBlocked("INVALID_NATIVE_REPLAY")
    elif not payload["reviewed_json"] or _file_hash(payload["reviewed_json"]) != payload["reviewed_json_sha256"]:
        raise ReplayBlocked("REVIEWED_SOURCE_CHANGED")
    if not Path(payload["policy_dir"]).is_dir():
        raise ReplayBlocked("POLICY_EVIDENCE_DIRECTORY_MISSING")
    ref = _one(read_only,
      "SELECT run_id,build_id,period_start,period_end,weight_setting_version_id,"
      "threshold_setting_version_id,priority_condition_setting_version_id "
      "FROM priority_run WHERE run_id=%s", (run_id,))
    if str(ref["build_id"]) != str(payload["build_id"]) or str(ref["period_start"]) != payload["start"] or str(ref["period_end"]) != payload["end"]:
        raise ReplayBlocked("DB77_ROUND_SOURCE_CHANGED")
    for dbcol, pkey in (("weight_setting_version_id", "weight_setting_id"),
                        ("threshold_setting_version_id", "threshold_setting_id"),
                        ("priority_condition_setting_version_id", "priority_condition_setting_id")):
        if int(ref[dbcol]) != payload[pkey]:
            raise ReplayBlocked("DB77_SETTINGS_CHANGED")
    return payload


def _check(run: dict) -> str | None:
    try:
        from app.core import db
        _load_verified(run, db.read_only)
    except (OSError, ReplayBlocked, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return f"재실행 입력 검증 불가 ({type(exc).__name__})"
    return None


def _rerun(ref_table: str | None, ref_id: str | None, user_id: int | None) -> None:
    if ref_table != "priority_run" or not ref_id or not user_id:
        raise ReplayBlocked("AUTHORIZED_OPERATOR_AND_ROUND_REQUIRED")
    from app.core import db
    # Bind to the exact job selected in the UI; never guess among failed jobs.
    context = rerun.current()
    if context is None or context[1] != user_id:
        raise ReplayBlocked("REPLAY_UI_JOB_CONTEXT_REQUIRED")
    original_job_id = int(context[0])
    jobs = db.read_only("SELECT job_run_id, module, status, ref_table, ref_id "
                        "FROM job_run WHERE job_run_id=%s", (original_job_id,))
    if len(jobs) != 1 or jobs[0].get("ref_table") != ref_table or str(jobs[0].get("ref_id")) != str(ref_id):
        raise ReplayBlocked("REPLAY_JOB_IDENTITY_CHANGED")
    p = _load_verified(jobs[0], db.read_only)
    argv = [sys.executable, "-m", "scripts.run_official_priority",
        "--existing-run-id", str(p["existing_run_id"]),
        "--setting-id", str(p["setting_id"]), "--policy-dir", p["policy_dir"],
        "--weight-setting-id", str(p["weight_setting_id"]),
        "--threshold-setting-id", str(p["threshold_setting_id"]),
        "--priority-condition-setting-id", str(p["priority_condition_setting_id"]),
        "--start", p["start"], "--end", p["end"], "--build-id", p["build_id"],
        "--authorized-by", str(user_id), "--approval-reference", p["approval_reference"],
        "--rerun-triggered-by", str(user_id), "--rerun-of-job-id", str(original_job_id),
        "--commit-official"]
    if p["native_full_source"]:
        argv.extend(["--native-full-source", "--expected-audit-sha256", p["expected_audit_sha256"]])
    else:
        argv.extend(["--reviewed-json", p["reviewed_json"]])
    # Launching a fresh DB85 job; writer independently blocks preexisting DB78 rows.
    completed = subprocess.run(argv, cwd=str(_repo_root()), capture_output=True,
                               text=True, timeout=1800, check=False)
    if completed.returncode != 0:
        raise ReplayBlocked("REPLAY_CHILD_FAILED_CHECK_DB85_LOGS")


def register_engine_rerun() -> None:
    rerun.register_rerun("ENGINE", _rerun, check=_check)
