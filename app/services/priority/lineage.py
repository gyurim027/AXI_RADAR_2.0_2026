"""Read-only B07 provenance for existing 59/62/77, without inventing an FK.

59/77 linkage and 62/77 linkage are indirect. Matching labels alone are
not proof of an approved source snapshot or the exact setting used for a run.
"""
from __future__ import annotations

from app.core import db


def _cols(table: str, read_only):
    rows = read_only(
        "SELECT COLUMN_NAME AS name FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (table,))
    return {str(r['name']) for r in rows}


def read_run_lineage(run_id: int, read_only=None) -> dict | None:
    reader = read_only or db.read_only
    rows = reader("SELECT run_id, build_id, rule_version, created_at, note "
                  "FROM priority_run WHERE run_id=%s", (run_id,))
    if not rows:
        return None
    run = rows[0]
    setting_cols = _cols('setting_version', reader)
    required = {'setting_version_id','version_label','content_ref','approval_status','approved_at'}
    if not required <= setting_cols:
        setting = {'status':'SCHEMA_NOT_MATCHED','candidates':[], 'missing_columns':sorted(required-setting_cols)}
    elif not run.get('rule_version'):
        setting = {'status':'NO_RULE_VERSION','candidates':[]}
    else:
        found = reader("SELECT setting_version_id, version_label, content_ref, approval_status, approved_at "
                       "FROM setting_version WHERE version_label=%s ORDER BY setting_version_id", (run['rule_version'],))
        safe = [{k:r.get(k) for k in ('setting_version_id','version_label','content_ref','approval_status','approved_at')} for r in found]
        setting = {'status':'ONE_VERSION_MATCH_UNVERIFIED' if len(safe)==1 else ('AMBIGUOUS_VERSION' if safe else 'NO_VERSION_MATCH'),
                   'candidates':safe, 'match_basis':'77.rule_version = 62.version_label; NO_DIRECT_FK_OR_PER_RUN_POLICY_HASH'}
    build_cols = _cols('build_info', reader)
    if not build_cols:
        build = {'status':'BUILD_TABLE_OR_COLUMNS_MISSING', 'candidates':[]}
    elif 'build_id' not in build_cols:
        build = {'status':'NO_SHARED_BUILD_ID_COLUMN','available_columns':sorted(build_cols),'candidates':[]}
    elif not run.get('build_id'):
        build = {'status':'NO_RUN_BUILD_ID','candidates':[]}
    else:
        # Only provide non-sensitive structural identity, no SELECT * leaks.
        found = reader("SELECT build_id FROM build_info WHERE build_id=%s LIMIT 3", (run['build_id'],))
        build = {'status':'ONE_BUILD_ID_MATCH_UNVERIFIED' if len(found)==1 else ('AMBIGUOUS_BUILD_ID' if found else 'NO_BUILD_ID_MATCH'),
                 'candidates':[{'build_id':r['build_id']} for r in found],
                 'match_basis':'77.build_id = 59.build_info.build_id (string); NO_FOREIGN_KEY'}
    # Distinguish a valid value lookup from cryptographically attested provenance.
    return {'run_id':run['run_id'],'priority_run':run,'setting_version':setting,'build_info':build,
            'end_to_end_verified':False,'evidence_status':'INDIRECT_LOOKUP_ONLY',
            'verification_gaps':['NO_77_SETTING_VERSION_ID_FK','NO_VERIFIED_59_77_BUILD_SNAPSHOT_ATTESTATION',
                                 'NO_PER_RUN_62_CONTENT_REF_SNAPSHOT'], 'db_writes':0}
