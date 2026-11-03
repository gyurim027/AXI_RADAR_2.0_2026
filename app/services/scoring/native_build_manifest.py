"""Proposed DB59 row_id manifest binding; no connections, writes or activation.

Uses existing row_id/table_name/file/rows/cols/built_at/script/note columns.
Metadata verification cannot prove that a supplied source fingerprint was
computed from the live source, or authorize an official R02 run.
"""
from hashlib import sha256
import json
import re
from datetime import date, datetime

from app.services.scoring.setting_links import _pairs, _invalid_constant
from app.services.scoring.source_audit_lineage import revalidate_source_audit, valid_hash

SCHEMA = 'RADAR_NATIVE_BUILD_MANIFEST_V1'
TABLE_NAME = 'RADAR_INPUT_SNAPSHOT_V1'
SETTING_FIELDS = ('weight_setting_version_id', 'threshold_setting_version_id', 'priority_condition_setting_version_id')
KEYS = {'schema','period_start','period_end','source_rows','grid_rows','grid_columns',
        'source_snapshot_sha256','grid_snapshot_sha256','eligible_counts_sha256',
        'aggregate_audit_sha256','policy_sha256','setting_ids'}

class NativeBuildBlocked(ValueError): pass

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')

def _validate(doc):
    if not isinstance(doc,dict) or set(doc) not in (KEYS, KEYS | {'source_audit_document'}) or doc.get('schema') != SCHEMA:
        raise NativeBuildBlocked('NATIVE_MANIFEST_SCHEMA_MISMATCH')
    for field in ('source_snapshot_sha256','grid_snapshot_sha256','eligible_counts_sha256','aggregate_audit_sha256','policy_sha256'):
        valid_hash(doc[field])
    if doc['source_snapshot_sha256'] == doc['aggregate_audit_sha256']:
        raise NativeBuildBlocked('AGGREGATE_AUDIT_IS_NOT_SOURCE_SNAPSHOT')
    for key in ('source_rows','grid_rows','grid_columns'):
        if type(doc[key]) is not int or doc[key] <= 0:
            raise NativeBuildBlocked('NATIVE_MANIFEST_COUNT_INVALID')
    ids=doc['setting_ids']
    if not isinstance(ids,list) or len(ids)!=3 or any(type(i) is not int or not 1<i<=9223372036854775807 for i in ids) or len(set(ids))!=3:
        raise NativeBuildBlocked('NATIVE_MANIFEST_THREE_SETTINGS_REQUIRED')
    try:
        start=date.fromisoformat(doc['period_start']);end=date.fromisoformat(doc['period_end'])
    except (ValueError,TypeError):
        raise NativeBuildBlocked('NATIVE_MANIFEST_PERIOD_INVALID') from None
    if start>end or start.isoformat()!=doc['period_start'] or end.isoformat()!=doc['period_end']:
        raise NativeBuildBlocked('NATIVE_MANIFEST_PERIOD_INVALID')
    if 'source_audit_document' in doc:
        from app.services.scoring.source_audit_lineage import verify_source_audit
        checked = verify_source_audit(canonical(doc['source_audit_document']),
            expected_sha256=doc['aggregate_audit_sha256'],start=start,end=end,grid_count=doc['grid_rows'])
        if json.loads(checked.raw)['source_rows'] != doc['source_rows']:
            raise NativeBuildBlocked('NATIVE_PERSISTED_AUDIT_COUNT_MISMATCH')
    return doc

def plan_native_build(*, source_snapshot_sha256, grid_snapshot_sha256, eligible_counts_sha256,
                      source_rows, grid_rows, grid_columns, policy_sha256, setting_ids, audit, built_at):
    """Prepare an unsigned DB59 record. Caller must verify fingerprints upstream.

    No SQL or DB approval is performed. This is a proposed new-row contract,
    never a reinterpretation or alteration of existing 63 reference records.
    """
    checked=revalidate_source_audit(audit,start=audit.period_start,end=audit.period_end)
    aggregate=json.loads(checked.raw)
    if source_rows!=aggregate['source_rows'] or grid_rows!=aggregate['grid_count']:
        raise NativeBuildBlocked('SNAPSHOT_COUNTS_DISAGREE_WITH_AUDIT')
    if not isinstance(built_at,datetime) or built_at.tzinfo is None or built_at.utcoffset() is None:
        raise NativeBuildBlocked('TIMEZONE_AWARE_BUILD_TIME_REQUIRED')
    doc=_validate({'schema':SCHEMA,'period_start':checked.period_start.isoformat(),'period_end':checked.period_end.isoformat(),
      'source_rows':source_rows,'grid_rows':grid_rows,'grid_columns':grid_columns,
      'source_snapshot_sha256':source_snapshot_sha256,'grid_snapshot_sha256':grid_snapshot_sha256,
      'eligible_counts_sha256':eligible_counts_sha256,'aggregate_audit_sha256':checked.audit_sha256,
      'policy_sha256':policy_sha256,'setting_ids':list(setting_ids)})
    payload=canonical(doc)
    return {'table_name':TABLE_NAME,'file':'sha256:'+sha256(payload).hexdigest(),'rows':grid_rows,'cols':grid_columns,
            'built_at':built_at.isoformat(),'script':SCHEMA,'note':payload.decode('ascii')}

def native_build_id(row_id):
    if type(row_id) is not int or not 0<row_id<=9223372036854775807:
        raise NativeBuildBlocked('NATIVE_BUILD_ROW_ID_INVALID')
    return 'db59:'+str(row_id)

def read_manifest(row):
    if row.get('table_name')!=TABLE_NAME or row.get('script')!=SCHEMA:
        raise NativeBuildBlocked('LEGACY_OR_UNSUPPORTED_BUILD_RECORD')
    raw=row.get('note')
    if not isinstance(raw,str) or len(raw.encode('utf8'))>16384:
        raise NativeBuildBlocked('NATIVE_BUILD_NOTE_INVALID')
    doc=_validate(json.loads(raw,object_pairs_hook=_pairs,parse_constant=_invalid_constant))
    if row.get('file')!='sha256:'+sha256(canonical(doc)).hexdigest():
        raise NativeBuildBlocked('NATIVE_BUILD_MANIFEST_HASH_MISMATCH')
    if row.get('rows')!=doc['grid_rows'] or row.get('cols')!=doc['grid_columns']:
        raise NativeBuildBlocked('NATIVE_BUILD_RECORD_COUNTS_MISMATCH')
    return doc

def verify_native_binding(run, row):
    rid=run.get('run_id')
    if type(rid) is not int or rid<=1:
        raise NativeBuildBlocked('LEGACY_RUN1_ACCESS_BLOCKED')
    if run.get('build_id')!=native_build_id(row.get('row_id')):
        raise NativeBuildBlocked('NATIVE_BUILD_ROW_REFERENCE_MISMATCH')
    doc=read_manifest(row)
    if run.get('note')!='r03:'+doc['aggregate_audit_sha256']:
        raise NativeBuildBlocked('NATIVE_BUILD_RUN_AUDIT_MISMATCH')
    if [run.get(k) for k in SETTING_FIELDS]!=doc['setting_ids']:
        raise NativeBuildBlocked('NATIVE_BUILD_RUN_SETTINGS_MISMATCH')
    if any(str(run.get(k))!=doc[k] for k in ('period_start','period_end')):
        raise NativeBuildBlocked('NATIVE_BUILD_RUN_PERIOD_MISMATCH')
    return {'status':'MANIFEST_BINDING_VERIFIED','run_id':rid,'build_id':run['build_id'],
            'build_row_id':row['row_id'],'manifest_sha256':row['file'][7:],
            'aggregate_audit_sha256':doc['aggregate_audit_sha256'],
            'source_snapshot_sha256':doc['source_snapshot_sha256'],
            'source_snapshot_recomputed':False,'official_audit_approval_verified':False,
            'official_write_authorized':False,'end_to_end_verified':False,'db_writes':0}

def read_native_binding(run, reader):
    if type(run.get('run_id')) is not int or run['run_id']<=1:
        raise NativeBuildBlocked('LEGACY_RUN1_ACCESS_BLOCKED')
    ref=run.get('build_id')
    if not isinstance(ref,str) or re.fullmatch(r'db59:[1-9][0-9]{0,18}',ref) is None:
        raise NativeBuildBlocked('NATIVE_BUILD_REFERENCE_REQUIRED')
    row_id=int(ref[5:]);native_build_id(row_id)
    rows=reader('SELECT row_id,table_name,file,`rows`,`cols`,built_at,script,note FROM build_info WHERE row_id=%s',(row_id,))
    if len(rows)!=1:
        raise NativeBuildBlocked('NATIVE_BUILD_RECORD_NOT_UNIQUE')
    return verify_native_binding(run,rows[0])

def validate_run_text_capacity(schema_rows, *, build_id, rule_version, note):
    """Check actual DB77 text widths without truncation, DDL, or DB access."""
    cols={r['column_name']:r for r in schema_rows if r['table_name']=='priority_run'}
    for field,value in [('build_id',build_id),('rule_version',rule_version),('note',note)]:
        column=cols.get(field,{})
        match=re.fullmatch(r'varchar\(([1-9][0-9]*)\)',str(column.get('column_type','')).lower())
        if not match or not isinstance(value,str):
            raise NativeBuildBlocked('DB77_TEXT_CAPACITY_UNVERIFIED:'+field)
        if len(value)>int(match[1]):
            raise NativeBuildBlocked('DB77_TEXT_CAPACITY_EXCEEDED:'+field)
    return {'status':'PASS','values_truncated':False,'db_writes':0}
