"""RADAR official existing-schema 62 -> C-07 -> score -> 77/78 entrypoint.

Run from repo root with explicit approved classification export. Never infers
human confirmation from AI-01 type candidate or C-08 preview-only records.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
from app.services.scoring.engine_rerun import save_replay_receipt

from app.core import db, job_run
from app.core.job_run import track
from app.services.scoring.operational_scoring import run_from_live_rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--existing-run-id',type=int,required=True,help='Fresh D-10 run ID; legacy run 1 prohibited')
    p.add_argument('--setting-id',type=int,required=True)
    p.add_argument('--policy-dir',required=True)
    p.add_argument('--weight-setting-id',type=int,required=True)
    p.add_argument('--threshold-setting-id',type=int,required=True)
    p.add_argument('--priority-condition-setting-id',type=int,required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--reviewed-json',help='Actual confirmed C-08 export: list[dict], no sampled/test-only rows')
    source.add_argument('--native-full-source',action='store_true',help='Approved DB59 input build and DB70 source-audit review; no fabricated CONFIRMED export')
    p.add_argument('--expected-audit-sha256',help='Required for --native-full-source; immutable aggregate audit identity')
    p.add_argument('--start',type=date.fromisoformat,required=True)
    p.add_argument('--end',type=date.fromisoformat,required=True)
    p.add_argument('--build-id',required=True,help='Verified 05 build snapshot identity <=30 chars')
    p.add_argument('--authorized-by',required=True)
    p.add_argument('--approval-reference',required=True)
    p.add_argument('--commit-official',action='store_true',help='Write existing 77/78 (explicit operator action)')
    p.add_argument('--rerun-triggered-by',type=int,default=None,help=argparse.SUPPRESS)
    p.add_argument('--rerun-of-job-id',type=int,default=None,help=argparse.SUPPRESS)
    a=p.parse_args()
    if a.existing_run_id <= 1 or a.existing_run_id > 9223372036854775807:
        p.error('FRESH_D10_RUN_ID_REQUIRED_LEGACY_RUN1_PROHIBITED')
    if not a.commit_official:
        p.error('--commit-official is required to write; this command does not have a preview mode')
    if len(a.build_id)>30:
        p.error('build-id must fit priority_run.build_id VARCHAR(30)')
    # Team baseline 62/1 is explicitly marked internal-demo simulation.
    # Reject before creating an 85 job or attempting any 77/78 write.
    if a.setting_id == 1:
        p.error('SETTING_1_IS_INTERNAL_DEMO_ONLY: official 77/78 writes are prohibited')
    from app.services.scoring.setting_links import links_enabled
    if not links_enabled():
        p.error('DB77_V24_ACTIVATION_REQUIRED')
    refs=(a.weight_setting_id,a.threshold_setting_id,a.priority_condition_setting_id)
    if len(set(refs))!=3 or any(i<=1 or i>9223372036854775807 for i in refs):
        p.error('THREE_DISTINCT_NON_SIMULATED_SETTING_IDS_REQUIRED')
    if a.native_full_source:
        if not a.expected_audit_sha256:p.error('NATIVE_EXPECTED_AUDIT_SHA_REQUIRED')
        from app.services.scoring.input_builds import load_native_scoring_input
        proof=load_native_scoring_input(run_id=a.existing_run_id,build_id=a.build_id,setting_ids=refs,
            start=a.start,end=a.end,expected_audit_sha256=a.expected_audit_sha256)
        grids=proof['_inputs']['_grid_rows'];rows=proof['_inputs']['_source_rows']
        full_source=proof['_inputs']['_full_source_input']
    else:
        path=Path(a.reviewed_json)
        if not path.is_file():p.error('Confirmed classification JSON not found: '+str(path))
        rows=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(rows,list) or not rows:
            p.error('Confirmed classification export must be a nonempty array')
        if any(r.get('scope') in ('TEST_ONLY_NOT_OFFICIAL','TYPE_ONLY_LOCAL_UNAUTHENTICATED') for r in rows):
            p.error('Test/pre-review data cannot be used as official input')
    # Source of truth: live existing 05 grid rows. Never read the isolated experiment SQLite.
    if not a.native_full_source:grids=db.read_only('SELECT * FROM grid_feature')
    # Account for the FULL source population, but explicitly exclude rows with
    # no valid grid ID. Mapped rows still require exact human-reviewed ID coverage.
    from app.services.scoring.source_coverage import verify_coverage, CoverageBlocked
    source_rows = rows if a.native_full_source else db.read_only(
        'SELECT complaint_id, gid FROM src_complaint WHERE received_date BETWEEN %s AND %s',
        (a.start, a.end))
    in_scope_rows = [r for r in rows if a.start <= date.fromisoformat(str(r['received_date'])[:10]) <= a.end]
    if len(in_scope_rows) != len(rows):
        p.error('REVIEW_EXPORT_CONTAINS_OUT_OF_PERIOD_ROWS')
    try:
        coverage = ({'source_audit_sha256':a.expected_audit_sha256,'native_build_id':a.build_id,
                     'source_rows':len(rows),'grid_count':len(grids)} if a.native_full_source else
                    verify_coverage(source_rows, in_scope_rows,{str(g['ID_gid']) for g in grids}))
    except CoverageBlocked as exc:
        p.error(str(exc))
    # This local audit record contains only counts and SHA-256 digests, no PII.
    out_dir = Path('out')
    out_dir.mkdir(exist_ok=True)
    manifest = out_dir / 'RADAR_R01_공간매핑_제외계약.json'
    manifest.write_text(json.dumps({'period_start':str(a.start),
        'period_end':str(a.end), **coverage}, ensure_ascii=False,
        indent=2)+'\n', encoding='utf-8')
    with track("\uC0B0\uC815", f"RADAR official priority scoring ({a.start}~{a.end})",
               module="ENGINE", ref_table="priority_run", ref_id=a.existing_run_id,
               triggered_by=a.rerun_triggered_by) as job:
        if job.run_id is None:
            raise RuntimeError("OFFICIAL_JOB_RECORD_UNAVAILABLE")
        # Replay evidence must be durable in DB85 before scoring starts.
        # Never replay a prior job without this receipt and its exact source digest.
        save_replay_receipt(job.run_id, a, db.read_only)
        if a.rerun_of_job_id is not None:
            job.log(f"ENGINE_RETRY_OF:{a.rerun_of_job_id}")

        result=run_from_live_rows(setting_version_id=a.setting_id,evidence_dir=a.policy_dir,
            build_id=a.build_id,start=a.start,end=a.end,grid_rows=grids,reviewed_rows=rows,
            authorized_by=a.authorized_by,approval_reference=a.approval_reference,
            explicit_db_write_approval=True,
            weight_setting_version_id=a.weight_setting_id,
            threshold_setting_version_id=a.threshold_setting_id,
            priority_condition_setting_version_id=a.priority_condition_setting_id,
            existing_run_id=a.existing_run_id,
            **({'r02_full_source_input':full_source} if a.native_full_source else {}))

        if (not isinstance(result, dict)
                or result.get("status") != "WRITTEN"
                or result.get("run_id") is None):
            raise RuntimeError("OFFICIAL_WRITE_RESULT_INVALID")

        job.ref("priority_run", result["run_id"])
        job.rows(result["candidate_count"])

    # The official result may already be committed. Never retry automatically.
    try:
        recorded = db.read_only(
            "SELECT status, ref_table, ref_id FROM job_run WHERE job_run_id=%s",
            (job.run_id,),
        )
    except Exception as exc:
        raise RuntimeError(
            "OFFICIAL_RESULT_SAVED_JOB_VERIFICATION_FAILED_DO_NOT_RERUN"
        ) from exc

    if (len(recorded) != 1
            or recorded[0].get("status") != job_run.SUCCESS
            or recorded[0].get("ref_table") != "priority_run"
            or str(recorded[0].get("ref_id")) != str(result["run_id"])):
        raise RuntimeError(
            "OFFICIAL_RESULT_SAVED_JOB_NOT_FINALIZED_DO_NOT_RERUN"
        )

    print(json.dumps(result,ensure_ascii=False,sort_keys=True,default=str))

if __name__=='__main__':main()
