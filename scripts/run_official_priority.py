"""RADAR official existing-schema 62 -> C-07 -> score -> 77/78 entrypoint.

Run from repo root with explicit approved classification export. Never infers
human confirmation from AI-01 type candidate or C-08 preview-only records.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path

from app.core import db, job_run
from app.core.job_run import track
from app.services.scoring.operational_scoring import run_from_live_rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--setting-id',type=int,required=True)
    p.add_argument('--policy-dir',required=True)
    p.add_argument('--reviewed-json',required=True,help='Actual confirmed C-08 export: list[dict], no sampled/test-only rows')
    p.add_argument('--start',type=date.fromisoformat,required=True)
    p.add_argument('--end',type=date.fromisoformat,required=True)
    p.add_argument('--build-id',required=True,help='Verified 05 build snapshot identity <=30 chars')
    p.add_argument('--authorized-by',required=True)
    p.add_argument('--approval-reference',required=True)
    p.add_argument('--commit-official',action='store_true',help='Write existing 77/78 (explicit operator action)')
    a=p.parse_args()
    if not a.commit_official:
        p.error('--commit-official is required to write; this command does not have a preview mode')
    if len(a.build_id)>30:
        p.error('build-id must fit priority_run.build_id VARCHAR(30)')
    path=Path(a.reviewed_json)
    if not path.is_file():p.error('Confirmed classification JSON not found: '+str(path))
    rows=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(rows,list) or not rows:
        p.error('Confirmed classification export must be a nonempty array')
    if any(r.get('scope') in ('TEST_ONLY_NOT_OFFICIAL','TYPE_ONLY_LOCAL_UNAUTHENTICATED') for r in rows):
        p.error('Test/pre-review data cannot be used as official input')
    # The full applicable complaint population must be accounted for. A one-row
    # review export cannot silently stand for 281k source records.
    population = db.read_only(
        'SELECT COUNT(*) AS n FROM src_complaint WHERE received_date BETWEEN %s AND %s',
        (a.start, a.end))
    expected = int(population[0]['n'])
    in_scope = sum(1 for r in rows if a.start <= date.fromisoformat(str(r['received_date'])[:10]) <= a.end)
    if in_scope != expected:
        p.error(f'INCOMPLETE_HUMAN_REVIEW_POPULATION: exported={in_scope} source={expected}')
    # Source of truth: live existing 05 grid rows. Never read the isolated experiment SQLite.
    grids=db.read_only('SELECT * FROM grid_feature')
    with track("\uC0B0\uC815", f"RADAR official priority scoring ({a.start}~{a.end})",
               module="ENGINE", triggered_by=None) as job:
        if job.run_id is None:
            raise RuntimeError("OFFICIAL_JOB_RECORD_UNAVAILABLE")

        result=run_from_live_rows(setting_version_id=a.setting_id,evidence_dir=a.policy_dir,
            build_id=a.build_id,start=a.start,end=a.end,grid_rows=grids,reviewed_rows=rows,
            authorized_by=a.authorized_by,approval_reference=a.approval_reference,
            explicit_db_write_approval=True)

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
