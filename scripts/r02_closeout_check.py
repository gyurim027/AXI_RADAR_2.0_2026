"""Read-only PC evidence collection. No approvals, DB writes, scoring or DB77 reads."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

DEFAULT_PROJECT = r'C:\Users\user\Projects\RADAR_team_review_20261030_105044'
POLICY_PATH = '_priority_next_execution/r01_hazard_policy_approved_20261101_033116_004891/integrated_policy_draft_hazard_missing_approved.json'
AUDIT_PATH = '_priority_next_execution/r02_full_source_quarantine_20261101_012021/full_source_policy_audit.json'
POLICY_SHA = 'f28a608c2593750b44dce44ddb5f68128df229e7eb0b00082c963d0ac545da81'
AUDIT_SHA = 'abed6e98e083564e935a11d50f4142dc99ae5aa67823c5112c7c012fe85f857f'
START, END = date(2021, 1, 1), date(2026, 9, 30)

class CollectionBlocked(ValueError): pass

def _hash(path):
    h=sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def checkpoint_digest(path):
    # SQLite WAL can contain committed rows absent from the main file.
    files=[path,Path(str(path)+'-wal')]
    state=[(label,_hash(p) if p.is_file() and p.stat().st_size else None)
           for label,p in zip(('main','wal'),files)]
    return sha256(json.dumps(state,separators=(',',':')).encode()).hexdigest()

def read_checkpoint(path):
    before=checkpoint_digest(path)
    con=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=3)
    try:
        con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
        statuses=dict(con.execute('SELECT status,COUNT(*) FROM result GROUP BY status'))
        if statuses!={'ok':160352,'mask_failed':75,'error':1}:
            raise CollectionBlocked('CHECKPOINT_POPULATION_MISMATCH')
        if con.execute('SELECT COUNT(*) FROM source').fetchone()[0]!=160428:
            raise CollectionBlocked('CHECKPOINT_SOURCE_COUNT_MISMATCH')
        orphaned=con.execute("SELECT COUNT(*) FROM result r WHERE r.status IN ('mask_failed','error') AND NOT EXISTS (SELECT 1 FROM source s WHERE s.cid=r.cid)").fetchone()[0]
        if orphaned:
            raise CollectionBlocked('CHECKPOINT_EXCEPTION_ABSENT_FROM_SOURCE')
        rows=[{'cid':r[0],'status':r[1]} for r in con.execute(
            "SELECT cid,status FROM result WHERE status IN ('mask_failed','error') ORDER BY cid")]
        if len(rows)!=76 or len({str(x['cid']) for x in rows})!=76:
            raise CollectionBlocked('CHECKPOINT_EXCEPTION_IDENTITIES_INVALID')
        if checkpoint_digest(path)!=before:
            raise CollectionBlocked('CHECKPOINT_CHANGED_DURING_READ')
        return rows,before
    finally:
        con.rollback();con.close()

def find_checkpoint(project,explicit=None):
    if explicit:
        rows,digest=read_checkpoint(explicit);return explicit,rows,digest
    roots=[project,project.parent/'RADAR_priority_integration_261028',
           project.parent/'RADAR_develop_20261025']
    found=[]; examined=0
    for root in roots:
        if not root.is_dir():continue
        for folder,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in
                ('node_modules','__pycache__','data','frontend','backend','samples')
                and 'backup' not in d.lower() and not (Path(folder)/d).is_symlink())
            for name in sorted(files):
                path=Path(folder)/name
                if path.suffix.lower() not in ('.db','.sqlite','.sqlite3') or path.is_symlink():continue
                examined+=1
                if examined>300:raise CollectionBlocked('CHECKPOINT_SCAN_LIMIT')
                try:
                    # Screen schema/counts before hashing a possibly large file.
                    # The selected checkpoint is reopened and fully checked below.
                    probe=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=3)
                    try:
                        statuses=dict(probe.execute('SELECT status,COUNT(*) FROM result GROUP BY status'))
                        if statuses!={'ok':160352,'mask_failed':75,'error':1}:continue
                    finally:probe.close()
                    rows,digest=read_checkpoint(path)
                    found.append((path,rows,digest))
                except (CollectionBlocked,sqlite3.Error,OSError):continue
    if not found:raise CollectionBlocked('FINAL_CHECKPOINT_NOT_FOUND_USE_CHECKPOINT_ARGUMENT')
    signatures={tuple(sorted((str(r['cid']),r['status']) for r in rows)) for _,rows,_ in found}
    if len(signatures)!=1:raise CollectionBlocked('MULTIPLE_DIFFERENT_FINAL_CHECKPOINTS')
    return found[0]

class ReadSession:
    """Finite SQL operations: no caller-supplied SQL accepted for source reads."""
    def __init__(self,con,stream_cursor=None):
        self.con=con;self.stream_cursor=stream_cursor;self.query_kinds=[]
    def cursor(self,kind,args=()):
        sql={
          'begin':'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY',
          'engines':"SELECT TABLE_NAME,ENGINE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('src_complaint','grid_feature','setting_version')",
          'grids':'SELECT ID_gid FROM grid_feature ORDER BY ID_gid',
          'source':'SELECT complaint_id,gid,received_date,relevance,class_method,ped_type FROM src_complaint WHERE received_date >= %s AND received_date < %s ORDER BY complaint_id',
          'settings':'SELECT setting_version_id,setting_kind,content_ref,version_label,approval_status,approved_at FROM setting_version WHERE content_ref=%s ORDER BY setting_version_id',
          'references':'SELECT setting_version_id,setting_kind,content_ref,version_label,NULL AS version_no,approval_status,approved_at FROM setting_version WHERE setting_version_id IN (%s,%s,%s)',
        }.get(kind)
        if sql is None:raise CollectionBlocked('QUERY_NOT_ALLOWED')
        cur=self.con.cursor(self.stream_cursor) if kind=='source' and self.stream_cursor else self.con.cursor()
        self.query_kinds.append(kind)
        try:cur.execute(sql,args)
        except Exception:cur.close();raise
        return cur
    def rows(self,kind,args=()):
        cur=self.cursor(kind,args)
        try:return list(cur.fetchall())
        finally:cur.close()
    def reference_reader(self,sql,args):
        # prepare_references is the existing contract; reject any new SQL shape.
        expected='SELECT setting_version_id,setting_kind,content_ref,version_label,NULL AS version_no,approval_status,approved_at FROM setting_version WHERE setting_version_id IN (%s,%s,%s)'
        if sql!=expected:raise CollectionBlocked('REFERENCE_QUERY_NOT_ALLOWED')
        return self.rows('references',args)

def safe_reason(exc):
    # SQL exceptions can contain rows, credentials or hostnames. Export codes only.
    known=(CollectionBlocked,)
    from app.services.scoring.approved_inputs import InputBlocked
    from app.services.scoring.source_audit_lineage import SourceAuditBlocked
    from app.services.scoring.policy_preflight import PolicyPreflightBlocked
    from app.services.scoring.setting_links import SettingLinksBlocked
    if isinstance(exc,known+(InputBlocked,SourceAuditBlocked,PolicyPreflightBlocked,SettingLinksBlocked)):
        return str(exc).split(':',1)[0]
    return type(exc).__name__

def run(project,checkpoint=None,connection_factory=None,stream_cursor=None):
    project=project.resolve()
    if not (project/'app').is_dir():raise CollectionBlocked('PROJECT_NOT_FOUND')
    sys.path.insert(0,str(project))
    from app.services.scoring.policy_preflight import store_policy_evidence
    from app.services.scoring.source_audit_lineage import verify_source_audit,store_source_audit
    from app.services.scoring import setting_links
    # The downloaded bundle supplies the same module as the source patch.
    module_path=Path(__file__).resolve().parent/'r02_exception_link.py'
    if module_path.is_file():
        spec=importlib.util.spec_from_file_location('radar_closeout_join',module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        reconcile_exceptions=module.reconcile_exceptions
    else:
        from app.services.scoring.r02_exception_link import reconcile_exceptions
    out=project/'_priority_next_execution/unattended_integration'/('r02_closeout_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%fZ'))
    out.mkdir(parents=True)
    report={'executed':True,'status':'IN_PROGRESS','db_writes':0,'commit_called':False,
       'run1_accessed':False,'database_connections':0,'classification_rerun':0,
       'scoring_executed':False,'official_approval_created':False,
       'official_run_created':False,'official_write_authorized':False,'stages':{},
       'evidence_paths':['R02_CLOSEOUT_REPORT.json','evidence/']}
    path=out/'R02_CLOSEOUT_REPORT.json'
    save=lambda:path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    save();exceptions=None;con=None;session=None
    try:
        raw=(project/POLICY_PATH).read_bytes()
        pre=store_policy_evidence(raw,out/'evidence',expected_sha256=POLICY_SHA)
        audit_raw=(project/AUDIT_PATH).read_bytes()
        receipt=verify_source_audit(audit_raw,expected_sha256=AUDIT_SHA,start=START,end=END,grid_count=2406)
        store_source_audit(receipt,out/'evidence')
        report['stages']['local_evidence']={'executed':True,'status':'PASS','policy_sha256':POLICY_SHA,'audit_sha256':AUDIT_SHA}
        try:
            checkpoint_path,exceptions,checkpoint_sha=find_checkpoint(project,checkpoint)
            report['checkpoint_evidence_path']=str(checkpoint_path)
            report['stages']['checkpoint']={'executed':True,'status':'PASS','exception_count':76,'checkpoint_sha256':checkpoint_sha}
        except Exception as exc:
            report['stages']['checkpoint']={'executed':True,'status':'BLOCKED','reason':safe_reason(exc)}
        if connection_factory is None:
            from app.core.db import raw_connection
            from pymysql.cursors import SSDictCursor
            connection_factory=raw_connection;stream_cursor=SSDictCursor
        con=connection_factory();report['database_connections']=1
        session=ReadSession(con,stream_cursor);session.rows('begin')
        engines={r['TABLE_NAME']:str(r['ENGINE']).upper() for r in session.rows('engines')}
        # Independent DB62 checks continue even if the checkpoint is unavailable.
        try:
            if engines.get('setting_version')!='INNODB':raise CollectionBlocked('SETTINGS_SNAPSHOT_ENGINE_INVALID')
            settings=session.rows('settings',('sha256:'+POLICY_SHA,))
            approved=[r for r in settings if r['approval_status'] in ('승인','APPROVED') and r['approved_at']]
            by_kind={k:[r for r in approved if r['setting_kind']==k] for k in setting_links.KINDS}
            if any(len(v)!=1 for v in by_kind.values()):
                raise CollectionBlocked('THREE_UNIQUE_APPROVED_SETTINGS_NOT_AVAILABLE')
            ids=tuple(by_kind[k][0]['setting_version_id'] for k in setting_links.KINDS)
            # Honor the actual deployment feature flag; never activate v24 here.
            document=setting_links.read_document(by_kind[setting_links.KINDS[0]][0],out/'evidence')
            refs=setting_links.prepare_references(session.reference_reader,ids,out/'evidence',document)
            report['stages']['db62']={'executed':True,'status':'PASS','setting_ids':[r.setting_version_id for r in refs],'approval_source':'EXISTING_DATABASE_ROWS','approval_created':False}
        except Exception as exc:
            report['stages']['db62']={'executed':True,'status':'BLOCKED','reason':safe_reason(exc)}
        if exceptions is not None:
            try:
                if any(engines.get(t)!='INNODB' for t in ('src_complaint','grid_feature')):
                    raise CollectionBlocked('SOURCE_SNAPSHOT_ENGINE_INVALID')
                gids=[r['ID_gid'] for r in session.rows('grids')]
                if len(gids)!=2406 or len({str(g) for g in gids})!=2406 or None in gids:
                    raise CollectionBlocked('GRID_POPULATION_INVALID')
                cur=session.cursor('source',(START.isoformat(),'2026-10-01'))
                def rows():
                    while True:
                        batch=cur.fetchmany(4096)
                        if not batch:return
                        yield from batch
                try:
                    link=reconcile_exceptions(exceptions,rows(),gids=gids,audit_raw=audit_raw,
                        expected_audit_sha256=AUDIT_SHA,checkpoint_sha256=checkpoint_sha,start=START,end=END)
                finally:cur.close()
                report['stages']['exception_link']={'executed':True,**link}
            except Exception as exc:
                report['stages']['exception_link']={'executed':True,'status':'BLOCKED','reason':safe_reason(exc)}
        else:
            report['stages']['exception_link']={'executed':False,'status':'BLOCKED','reason':'CHECKPOINT_REQUIRED'}
    except Exception as exc:
        report['blocker']=safe_reason(exc)
    finally:
        if exceptions is not None:exceptions.clear()
        if con is not None:
            try:con.rollback()
            except Exception as exc:report['blocker']='READ_TRANSACTION_CLEANUP_'+type(exc).__name__
            try:con.close()
            except Exception as exc:report['blocker']='CONNECTION_CLOSE_'+type(exc).__name__
        report['query_kinds']=session.query_kinds if session else []
        expected=('local_evidence','checkpoint','db62','exception_link')
        for stage in expected:
            report['stages'].setdefault(stage,{'executed':False,'status':'BLOCKED','reason':'PREREQUISITE_NOT_AVAILABLE'})
        report['status']='PASS' if all(report['stages'].get(k,{}).get('status')=='PASS' for k in expected) and not report.get('blocker') else 'BLOCKED'
        report['readiness_scope']='EVIDENCE_AND_EXISTING_SETTINGS_ONLY'
        report['remaining_conditions']=['OFFICIAL_AUDIT_APPROVAL_AND_EXECUTION_GATE','NEW_DB59_DB77_INPUT_BINDING','NEW_DB78_DB85_API_UI_INTEGRATION']
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    return report,path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path(DEFAULT_PROJECT))
    p.add_argument('--checkpoint',type=Path)
    args=p.parse_args()
    try:
        report,path=run(args.project,args.checkpoint)
        print(json.dumps({'status':report['status'],'stages':{k:v['status'] for k,v in report['stages'].items()},'db_writes':0,'run1_accessed':False,'report':str(path)},ensure_ascii=False))
        return 0 if report['status']=='PASS' else 2
    except Exception:
        print(json.dumps({'status':'BLOCKED','reason':'PROJECT_OR_RUNTIME_UNAVAILABLE','db_writes':0,'run1_accessed':False}));return 2

if __name__=='__main__':sys.exit(main())
