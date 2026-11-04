"""Read-only B07 provenance for existing 59/62/77, without inventing an FK.

59/77 linkage and 62/77 linkage are indirect. Matching labels alone are
not proof of an approved source snapshot or the exact setting used for a run.
"""
from __future__ import annotations

from app.core import db
from app.services.scoring.setting_links import links_enabled, attach_run_versions


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
    direct_mode = links_enabled()
    if direct_mode:
        run = attach_run_versions([run], reader, True)[0]
        setting = {'status':'DIRECT_REFERENCE_LOOKUP', 'versions':run['setting_versions'],
                   'match_basis':'77 explicit setting IDs -> 62 setting_version_id',
                   'content_hash_verified_by_this_query':False}
    else:
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
    if isinstance(run.get('build_id'),str) and run['build_id'].startswith('db59:'):
        from app.services.scoring.native_build_manifest import read_native_binding
        refs = reader('SELECT run_id,period_start,period_end,weight_setting_version_id,'
                      'threshold_setting_version_id,priority_condition_setting_version_id '
                      'FROM priority_run WHERE run_id=%s',(run_id,))
        if len(refs)!=1:
            raise ValueError('NATIVE_RUN_REFERENCE_MISSING')
        build = read_native_binding({**run,**refs[0]},reader)
        build['match_basis']='77.build_id db59:<row_id> -> 59.row_id; manifest/audit/settings/period verified; no physical FK'
    elif not build_cols:
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
    native_lookup = build.get('status') == 'MANIFEST_BINDING_VERIFIED'
    gaps = (['CURRENT_INPUT_NOT_RECOMPUTED_BY_LINEAGE_LOOKUP','DB70_APPROVAL_NOT_CHECKED_BY_LINEAGE_LOOKUP',
             'CURRENT_DB62_CONTENT_NOT_RECHECKED_BY_LINEAGE_LOOKUP'] if native_lookup else
            ['NO_VERIFIED_59_77_BUILD_SNAPSHOT_ATTESTATION','NO_PER_RUN_62_CONTENT_REF_SNAPSHOT'])
    return {'run_id':run['run_id'],'priority_run':run,'setting_version':setting,'build_info':build,
            'end_to_end_verified':False,'evidence_status':('NATIVE_BUILD_MANIFEST_LOOKUP_EXECUTION_NOT_ATTESTED' if native_lookup else 'DIRECT_SETTING_LOOKUP_BUILD_UNVERIFIED' if direct_mode else 'INDIRECT_LOOKUP_ONLY'),
            'verification_gaps':([] if direct_mode and all(run.get(f) is not None for f in
                ('weight_setting_version_id','threshold_setting_version_id','priority_condition_setting_version_id'))
                else ['NO_COMPLETE_77_SETTING_REFERENCES']) + gaps, 'db_writes':0}
