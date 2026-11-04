"""Native DB59 snapshot registration and durable DB70 audit approval.

No DDL or official-run/candidate/job writes. Current source fingerprints must
be recomputed at registration, review and execution; an aggregate hash alone
is never accepted as proof of source identity. No complaint data is returned.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math

from app.services.scoring import native_build_manifest as native
from app.services.scoring.source_audit_lineage import verify_source_audit
from app.services.scoring.r02_full_source_quarantine import prepare_full_source_r02

CREATE_REASON = 'RADAR_INPUT_BUILD_REGISTERED_V1'
APPROVE_REASON = 'RADAR_FULL_SOURCE_AUDIT_APPROVED_V1'
BUILD_COLUMNS = 'row_id,table_name,file,`rows`,`cols`,built_at,script,note'
SOURCE_SQL = ('SELECT complaint_id,gid,received_date,relevance,class_method,ped_type,coord_accuracy FROM src_complaint '
              'WHERE received_date >= %s AND received_date < %s ORDER BY complaint_id')

class BuildBlocked(ValueError): pass
class BuildCommitUnconfirmed(RuntimeError): pass

def _actor(user, role):
    if user.get('role') != role or type(user.get('user_id')) is not int or user['user_id']<=0 or user.get('read_only'):
        raise BuildBlocked('BUILD_AUTHENTICATED_ROLE_REQUIRED')
    return user['user_id']

def _value(v):
    if v is None or type(v) in (str,int,bool): return v
    if isinstance(v,(date,datetime)): return {'date':v.isoformat()}
    if isinstance(v,Decimal):
        if not v.is_finite(): raise BuildBlocked('NONFINITE_SNAPSHOT_VALUE')
        return {'decimal':str(v)}
    if type(v) is float and math.isfinite(v): return v
    raise BuildBlocked('UNSUPPORTED_SNAPSHOT_VALUE')

def fingerprint(rows, key):
    if not rows: raise BuildBlocked('EMPTY_SNAPSHOT')
    columns=set(rows[0]); seen=set(); packed=[]
    for row in rows:
        if set(row)!=columns or row.get(key) is None: raise BuildBlocked('SNAPSHOT_COLUMNS_OR_KEY_INVALID')
        identity=str(row[key])
        if not identity or identity in seen: raise BuildBlocked('SNAPSHOT_DUPLICATE_KEY')
        seen.add(identity)
        packed.append((identity,{k:_value(v) for k,v in row.items()}))
    return sha256(native.canonical(sorted(packed,key=lambda p:p[0]))).hexdigest()

def snapshot(source, grids, *, start, end, expected_audit_sha256):
    """One current input capture; reuse existing classifiers and aggregator unchanged."""
    ids = frozenset()
    receipt = None
    if (start.isoformat(),end.isoformat()) == ('2022-01-01','2025-12-31'):
        from app.services.scoring.r02_exception10_policy import (
            select_approved_exceptions, approved_exclusion_receipt, EXPECTED_COUNTS_SHA,
            DispositionBlocked)
        from pathlib import Path
        from scripts.r02_closeout_check import find_checkpoint
        root=Path(__file__).resolve().parents[3]
        _, failures, checkpoint_sha = find_checkpoint(root)
        ids = select_approved_exceptions(source, gids={str(r['ID_gid']) for r in grids},
             checkpoint_failures=failures, checkpoint_sha=checkpoint_sha,
             source_sha=fingerprint(source,'complaint_id'), start=start,end=end)
        receipt=approved_exclusion_receipt()
    full=prepare_full_source_r02(source,gids={str(r['ID_gid']) for r in grids},start=start,end=end,
        mapped_exclusion_policy=True,unmapped_quarantine_policy=True,
        exception_ids=ids,exception_receipt=receipt)
    if ids and fingerprint(list(full.prepared.counts_by_gid),'gid') != EXPECTED_COUNTS_SHA:
        raise BuildBlocked('EXCEPTION_APPROVED_GRID_COUNTS_MISMATCH')
    receipt=verify_source_audit(native.canonical(full.audit),expected_sha256=expected_audit_sha256,
        start=start,end=end,grid_count=len(grids))
    return {'source_snapshot_sha256':fingerprint(source,'complaint_id'),
            'grid_snapshot_sha256':fingerprint(grids,'ID_gid'),
            'eligible_counts_sha256':fingerprint(list(full.prepared.counts_by_gid),'gid'),
            'source_rows':len(source),'grid_rows':len(grids),'grid_columns':len(grids[0]),
            'receipt':receipt,'counts_by_gid':full.prepared.counts_by_gid,
            '_source_rows':source,'_grid_rows':grids,'_full_source_input':full}

def _capture(cur, start, end, expected):
    cur.execute(SOURCE_SQL,(start,end+timedelta(days=1))); source=list(cur.fetchall())
    cur.execute('SELECT * FROM grid_feature ORDER BY ID_gid'); grids=list(cur.fetchall())
    return snapshot(source,grids,start=start,end=end,expected_audit_sha256=expected)

def _key(row): return 'input_build:'+str(row['row_id'])+':'+row['file'][7:]

def _audit(cur, uid, kind, key, reason):
    cur.execute('INSERT INTO access_audit (actor_ref,resource_kind,resource_key,access_reason) VALUES (%s,%s,%s,%s)',
                (uid,kind,key,reason))

def _events(cur, row, kind, reason):
    cur.execute('SELECT access_audit_id,actor_ref,resource_kind,resource_key,access_reason,accessed_at '
                'FROM access_audit WHERE resource_kind=%s AND resource_key=%s AND access_reason=%s ORDER BY access_audit_id',
                (kind,_key(row),reason))
    return list(cur.fetchall())

def _settings(cur, doc):
    kinds=('가중치','기준값','우선 확인 조건')
    for sid,kind in zip(doc['setting_ids'],kinds):
        cur.execute('SELECT setting_version_id,setting_kind,content_ref,approval_status,approved_at '
                    'FROM setting_version WHERE setting_version_id=%s FOR UPDATE',(sid,))
        rows=list(cur.fetchall())
        if len(rows)!=1: raise BuildBlocked('BUILD_SETTING_MISSING')
        r=rows[0]
        if (r['setting_kind']!=kind or r['content_ref']!='sha256:'+doc['policy_sha256']
                or r['approval_status']!='승인' or not r['approved_at']):
            raise BuildBlocked('BUILD_SETTING_NOT_APPROVED_OR_MISMATCHED')

def _stored(cur, row_id):
    native.native_build_id(row_id)
    cur.execute('SELECT '+BUILD_COLUMNS+' FROM build_info WHERE row_id=%s FOR UPDATE',(row_id,))
    rows=list(cur.fetchall())
    if len(rows)!=1: raise BuildBlocked('BUILD_NOT_UNIQUE')
    row=rows[0];doc=native.read_manifest(row)
    if 'source_audit_document' not in doc: raise BuildBlocked('PERSISTED_SOURCE_AUDIT_REQUIRED')
    return row,doc

def _current(cur, doc):
    current=_capture(cur,date.fromisoformat(doc['period_start']),date.fromisoformat(doc['period_end']),doc['aggregate_audit_sha256'])
    for k in ('source_snapshot_sha256','grid_snapshot_sha256','eligible_counts_sha256','source_rows','grid_rows','grid_columns'):
        if current[k]!=doc[k]: raise BuildBlocked('CURRENT_INPUT_CHANGED:'+k)
    return current

def _approval(cur, row):
    created=_events(cur,row,'설정 변경',CREATE_REASON)
    approved=_events(cur,row,'승인',APPROVE_REASON)
    if len(created)!=1 or len(approved)!=1: raise BuildBlocked('UNIQUE_DURABLE_BUILD_APPROVAL_REQUIRED')
    if (not created[0].get('actor_ref') or not created[0].get('accessed_at') or not approved[0].get('actor_ref') or not approved[0].get('accessed_at')
            or str(created[0]['actor_ref'])==str(approved[0]['actor_ref'])):
        raise BuildBlocked('BUILD_SELF_APPROVAL_OR_METADATA_INVALID')
    return approved[0]

def _connection(factory):
    if factory is None:
        from app.core.db import raw_connection
        factory=raw_connection
    return factory()

def _begin(cur):
    cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    cur.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')

def _engines(cur):
    names=('build_info','access_audit','setting_version','src_complaint','grid_feature')
    cur.execute('SELECT TABLE_NAME AS table_name,ENGINE AS engine FROM INFORMATION_SCHEMA.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s,%s,%s,%s)',names)
    engines={r['table_name']:str(r['engine']).upper() for r in cur.fetchall()}
    if any(engines.get(t)!='INNODB' for t in names): raise BuildBlocked('BUILD_TRANSACTION_ENGINE_REQUIRED')

def register_build(*, user, start, end, expected_audit_sha256, policy_sha256, setting_ids,
                   explicit_registration_approval=False, connection_factory=None):
    uid=_actor(user,'operator')
    if explicit_registration_approval is not True: raise BuildBlocked('EXPLICIT_BUILD_REGISTRATION_REQUIRED')
    if type(start) is not date or type(end) is not date or start>end: raise BuildBlocked('BUILD_PERIOD_INVALID')
    con=_connection(connection_factory); locked=False; lock=None
    try:
        with con.cursor() as cur:
            _begin(cur)
            _engines(cur)
            s=_capture(cur,start,end,expected_audit_sha256)
            record=native.plan_native_build(**{k:s[k] for k in ('source_snapshot_sha256','grid_snapshot_sha256','eligible_counts_sha256','source_rows','grid_rows','grid_columns')},
                policy_sha256=policy_sha256,setting_ids=setting_ids,audit=s['receipt'],built_at=datetime.now(timezone.utc))
            doc=json.loads(record['note']);doc['source_audit_document']=json.loads(s['receipt'].raw)
            record['note']=native.canonical(doc).decode('ascii');record['file']='sha256:'+sha256(native.canonical(doc)).hexdigest()
            native.read_manifest(record)
            lock='db59:'+record['file'][7:65]
            cur.execute('SELECT GET_LOCK(%s,5) AS acquired',(lock,))
            if cur.fetchone().get('acquired')!=1: raise BuildBlocked('BUILD_LOCK_BUSY')
            locked=True
            cur.execute('SELECT '+BUILD_COLUMNS+' FROM build_info WHERE table_name=%s AND file=%s FOR UPDATE',(native.TABLE_NAME,record['file']))
            existing=list(cur.fetchall())
            if len(existing)>1: raise BuildBlocked('BUILD_DUPLICATE_MANIFEST')
            _settings(cur,doc)
            if existing:
                row=existing[0]
                if native.read_manifest(row)!=doc: raise BuildBlocked('BUILD_EXISTING_CONTENT_MISMATCH')
                events=_events(cur,row,'설정 변경',CREATE_REASON)
                if len(events)!=1 or events[0]['actor_ref']!=uid: raise BuildBlocked('BUILD_EXISTING_PROPOSER_MISMATCH')
            else:
                fields=('table_name','file','rows','cols','built_at','script','note')
                cur.execute('INSERT INTO build_info (table_name,file,`rows`,`cols`,built_at,script,note) VALUES (%s,%s,%s,%s,%s,%s,%s)',tuple(record[k] for k in fields))
                row_id=cur.lastrowid;row,stored=_stored(cur,row_id)
                if stored!=doc: raise BuildBlocked('BUILD_INSERT_READBACK_MISMATCH')
                _audit(cur,uid,'설정 변경',_key(row),CREATE_REASON)
        try: con.commit()
        except Exception: raise BuildCommitUnconfirmed('BUILD_COMMIT_UNCONFIRMED_DO_NOT_RETRY') from None
        return {'build_row_id':row['row_id'],'build_id':native.native_build_id(row['row_id']),
                'manifest_sha256':row['file'][7:],'created':not bool(existing),'audit_approved':False,
                'official_run_created':False,'scoring_authorized':False}
    except Exception:
        con.rollback();raise
    finally:
        try:
            if locked:
                with con.cursor() as cur:cur.execute('SELECT RELEASE_LOCK(%s)',(lock,))
        finally:con.close()

def approve_build(row_id, *, expected_manifest_sha256, user, explicit_approval=False, connection_factory=None):
    uid=_actor(user,'city')
    if explicit_approval is not True: raise BuildBlocked('EXPLICIT_SOURCE_AUDIT_APPROVAL_REQUIRED')
    con=_connection(connection_factory)
    try:
        with con.cursor() as cur:
            _begin(cur);_engines(cur);row,doc=_stored(cur,row_id)
            if row['file']!='sha256:'+expected_manifest_sha256: raise BuildBlocked('BUILD_EXPECTED_HASH_MISMATCH')
            events=_events(cur,row,'설정 변경',CREATE_REASON)
            if len(events)!=1 or events[0]['actor_ref']==uid: raise BuildBlocked('BUILD_SELF_APPROVAL_OR_CREATOR_MISSING')
            _settings(cur,doc);_current(cur,doc)
            existing=_events(cur,row,'승인',APPROVE_REASON)
            if existing: _approval(cur,row)
            else: _audit(cur,uid,'승인',_key(row),APPROVE_REASON);_approval(cur,row)
        try: con.commit()
        except Exception: raise BuildCommitUnconfirmed('BUILD_REVIEW_COMMIT_UNCONFIRMED_DO_NOT_RETRY') from None
        return {'build_row_id':row_id,'manifest_sha256':row['file'][7:],'audit_approved':True,
                'already_approved':bool(existing),'official_run_created':False,'scoring_authorized':False}
    except Exception:
        con.rollback();raise
    finally:con.close()

def verify_execution_build(cur, *, build_id, policy_sha256, setting_ids, start, end, include_inputs=False):
    """Re-read approval and recompute current inputs inside caller's transaction."""
    import re
    if not isinstance(build_id,str) or re.fullmatch(r'db59:[1-9][0-9]{0,18}',build_id) is None: raise BuildBlocked('NATIVE_BUILD_REFERENCE_REQUIRED')
    _engines(cur);row,doc=_stored(cur,int(build_id[5:]))
    if (doc['policy_sha256']!=policy_sha256 or doc['setting_ids']!=list(setting_ids)
            or doc['period_start']!=start.isoformat() or doc['period_end']!=end.isoformat()):
        raise BuildBlocked('EXECUTION_BUILD_CONTRACT_MISMATCH')
    _settings(cur,doc);approval=_approval(cur,row);current=_current(cur,doc)
    proof={'build_row_id':row['row_id'],'manifest_sha256':row['file'][7:],
            'approval_audit_id':approval['access_audit_id'],'source_audit_sha256':doc['aggregate_audit_sha256'],
            'current_input_verified':True,'official_audit_approval_verified':True,
            'source_audit':current['receipt'],'counts_by_gid':current['counts_by_gid'],
            'official_write_authorized':False}
    if include_inputs:
        proof['_inputs']={k:current[k] for k in ('_source_rows','_grid_rows','_full_source_input')}
    return proof

def load_native_scoring_input(*,run_id,build_id,setting_ids,start,end,expected_audit_sha256,connection_factory=None):
    """Read one new run and its current inputs in one snapshot; never create a job."""
    if type(run_id) is not int or run_id<=1: raise BuildBlocked('LEGACY_RUN1_ACCESS_BLOCKED')
    import re
    if not isinstance(build_id,str) or re.fullmatch(r'db59:[1-9][0-9]{0,18}',build_id) is None:
        raise BuildBlocked('NATIVE_BUILD_REFERENCE_REQUIRED')
    con=_connection(connection_factory)
    try:
        with con.cursor() as cur:
            _begin(cur);row,doc=_stored(cur,int(build_id[5:]))
            if expected_audit_sha256!=doc['aggregate_audit_sha256']: raise BuildBlocked('EXPECTED_AUDIT_MISMATCH')
            proof=verify_execution_build(cur,build_id=build_id,policy_sha256=doc['policy_sha256'],
                setting_ids=setting_ids,start=start,end=end,include_inputs=True)
            cur.execute('SELECT run_id,build_id,note,period_start,period_end,'+','.join(native.SETTING_FIELDS)+
                        ' FROM priority_run WHERE run_id=%s FOR UPDATE',(run_id,))
            runs=list(cur.fetchall())
            if len(runs)!=1: raise BuildBlocked('NEW_RUN_NOT_FOUND')
            native.verify_native_binding(runs[0],row)
            cur.execute('SELECT COUNT(*) AS n FROM priority_candidate WHERE run_id=%s',(run_id,))
            if cur.fetchone()['n']!=0: raise BuildBlocked('NEW_RUN_ALREADY_HAS_CANDIDATES')
            return proof
    finally:
        try:con.rollback()
        finally:con.close()

def verify_supplied_scoring_inputs(*,build_id,grids,source,policy_sha256,setting_ids,reader):
    """Bind the actual arrays handed to the calculator, as well as live DB state."""
    import re
    if not isinstance(build_id,str) or re.fullmatch(r'db59:[1-9][0-9]{0,18}',build_id) is None:
        raise BuildBlocked('NATIVE_BUILD_REFERENCE_REQUIRED')
    row_id=int(build_id[5:]);native.native_build_id(row_id)
    rows=reader('SELECT '+BUILD_COLUMNS+' FROM build_info WHERE row_id=%s',(row_id,))
    if len(rows)!=1: raise BuildBlocked('BUILD_NOT_UNIQUE')
    doc=native.read_manifest(rows[0])
    if doc['policy_sha256']!=policy_sha256 or doc['setting_ids']!=list(setting_ids):
        raise BuildBlocked('SUPPLIED_SCORING_POLICY_OR_SETTINGS_MISMATCH')
    if fingerprint(grids,'ID_gid')!=doc['grid_snapshot_sha256']:
        raise BuildBlocked('SUPPLIED_SCORING_GRID_MISMATCH')
    if fingerprint(source,'complaint_id')!=doc['source_snapshot_sha256']:
        raise BuildBlocked('SUPPLIED_SCORING_SOURCE_MISMATCH')
    return {'supplied_input_verified':True,'official_write_authorized':False}

def read_build_status(row_id, reader=None):
    native.native_build_id(row_id)
    if reader is None:
        from app.core.db import read_only
        reader=read_only
    rows=reader('SELECT '+BUILD_COLUMNS+' FROM build_info WHERE row_id=%s',(row_id,))
    if len(rows)!=1: raise BuildBlocked('BUILD_NOT_UNIQUE')
    row=rows[0];doc=native.read_manifest(row)
    events=reader('SELECT access_audit_id,actor_ref,resource_kind,access_reason,accessed_at FROM access_audit '
                  'WHERE resource_key=%s AND resource_kind IN (%s,%s) ORDER BY access_audit_id',(_key(row),'설정 변경','승인'))
    created=[r for r in events if r['resource_kind']=='설정 변경' and r['access_reason']==CREATE_REASON]
    approved=[r for r in events if r['resource_kind']=='승인' and r['access_reason']==APPROVE_REASON]
    verified=(len(created)==len(approved)==1 and bool(created[0].get('actor_ref'))
      and bool(approved[0].get('actor_ref')) and bool(approved[0].get('accessed_at'))
      and str(created[0]['actor_ref'])!=str(approved[0]['actor_ref']))
    return {'build_row_id':row_id,'build_id':native.native_build_id(row_id),'manifest_sha256':row['file'][7:],
            'manifest':doc,'audit_approved':bool(verified),'current_input_verified':False,
            'official_run_created':False,'scoring_authorized':False,'db_writes':0}
