"""Explicit experimental execution. SQLite only; no shared DB or approval writes."""
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
import argparse,json,sqlite3,hashlib
import numpy as np
import pandas as pd
from .calculation import Policy,calculate,normalize,rank_scores,FEATURES
from .evidence import canonical,digest,EvidenceStore
from .consumer import join_result

ROOT=Path(__file__).parent

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def execute(grid,complaints,config,database,*,fail_after=None):
    cfg=read_json(config)
    required={'schema_version','run_id','build_id','setting_version_id','policy','complaint_mode','coefficient_points','fit_population','comparison_population','input_status','period_note'}
    if set(cfg)!=required: raise ValueError('CONFIG_KEYS')
    if cfg['schema_version']!=1 or cfg['input_status']!='EXPLORATORY_PROXY': raise ValueError('OFFICIAL_EXECUTION_UNAVAILABLE')
    for k in ['run_id','setting_version_id']:
        if type(cfg[k]) is not int or cfg[k]<=0: raise ValueError('INVALID_ID')
    if not isinstance(cfg['build_id'],str) or not cfg['build_id'].strip() or not cfg['period_note']:raise ValueError('MISSING_PROVENANCE')
    if cfg['fit_population']!='all_input_positive_counts' or cfg['comparison_population']!='hazard_observed':raise ValueError('UNSUPPORTED_POPULATION')
    if cfg['complaint_mode'] not in ['independent','inside_hazard','bonus']:raise ValueError('MODE')
    q=cfg['coefficient_points']
    if type(q) not in [int,float] or not np.isfinite(q) or not 0<=q<=100:raise ValueError('COEFFICIENT')
    policy=Policy(**cfg['policy']);policy.validate()
    blobs={k:Path(v).read_bytes() for k,v in [('grid',grid),('complaints',complaints)]}
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()}
    code_hash=digest(''.join((ROOT/n).read_text(encoding='utf-8') for n in ['runtime.py','calculation.py']))
    fingerprint=digest(canonical({'config':cfg,'inputs':hashes,'code':code_hash}))
    f=pd.read_csv(BytesIO(blobs['grid']));a=pd.read_csv(BytesIO(blobs['complaints']))
    if f.ID_gid.isna().any() or not f.ID_gid.is_unique or a.gid.isna().any() or not a.gid.is_unique or set(a.gid)!=set(f.ID_gid):raise ValueError('GRID_POPULATION')
    a=a.set_index('gid').loc[f.ID_gid].reset_index()
    for col in ['complaint_all','complaint_lowexcluded','complaint_illustrative_filter']:
        v=pd.to_numeric(a[col],errors='raise')
        if v.isna().any() or not np.isfinite(v).all() or (v<0).any() or (v%1!=0).any():raise ValueError('COUNT:'+col)
        a[col]=v
    if (a.complaint_lowexcluded>a.complaint_all).any() or (a.complaint_illustrative_filter>a.complaint_all).any():raise ValueError('COUNT_SUBSET')
    ranked,domains,contributions,states=calculate(f,policy)
    b=ranked.score;s=normalize(a.complaint_illustrative_filter,policy.normalization);h=domains.hazard
    mode=cfg['complaint_mode'];term=q*s
    adjustment=-q/100*b if mode=='independent' else -q*h if mode=='inside_hazard' else pd.Series(0.,index=b.index)
    # Preserve original floating point operation order used by the regression fixtures.
    pre=(1-q/100)*b+term if mode=='independent' else b+q*(s-h) if mode=='inside_hazard' else b+term
    cap=(100-pre).clip(upper=0) if mode=='bonus' else pd.Series(0.,index=b.index)
    total=(pre+cap).where(h.notna());out=rank_scores(total,f.ID_gid)
    sid=cfg['setting_version_id'];run=cfg['run_id'];label=policy.label
    setting={'setting_version_id':sid,'setting_kind':'가중치','version_label':label,'content_ref':'isolated-config-sha256:'+digest(canonical(cfg)),'approval_status':'제안','approved_by':None,'approved_at':None,'policy':cfg,'input_sha256':hashes['grid']}
    snapshot=canonical(setting);snapshot_hash=digest(snapshot)
    manifest={'run_id':run,'build_id':cfg['build_id'],'input_sha256':hashes['grid'],'policies':[{**cfg,'label':label}],'inputs':hashes,'code_sha256':code_hash,'execution_fingerprint':fingerprint}
    # Existing join contract uses the exact policy stored in the setting snapshot.
    setting['policy']=manifest['policies'][0];snapshot=canonical(setting);snapshot_hash=digest(snapshot)
    database=Path(database);database.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(database,timeout=30) as c:
        c.execute('PRAGMA foreign_keys=ON');c.executescript((ROOT/'isolated_schema.sql').read_text(encoding='utf-8'))
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT note FROM priority_run WHERE run_id=?',(run,)).fetchone()
        if old:
            if old[0]!=fingerprint:raise ValueError('RUN_CONFLICT')
            if c.execute('SELECT COUNT(*) FROM evidence WHERE run_id=?',(run,)).fetchone()[0]!=len(f):raise ValueError('INCOMPLETE_RUN')
            for gid in f.ID_gid:read_result(database,run,gid)
            return {'run_id':run,'execution':'REUSED','rows':len(f)}
        if c.execute('SELECT 1 FROM setting_version WHERE setting_version_id=?',(sid,)).fetchone():raise ValueError('SETTING_ID_ALREADY_USED')
        c.execute('INSERT INTO setting_version(setting_version_id,setting_kind,version_label,content_ref,approval_status) VALUES (?,?,?,?,?)',(sid,'가중치',label,setting['content_ref'],'제안'))
        c.execute('INSERT INTO setting_snapshot VALUES (?,?,?)',(sid,snapshot,snapshot_hash))
        c.execute('INSERT INTO priority_run VALUES (?,?,?,?,?)',(run,cfg['build_id'],label,datetime.now(timezone.utc).isoformat(),fingerprint))
        for i,gid in enumerate(f.ID_gid):
            raw_gu=None if pd.isna(f.id_gu.iloc[i]) else str(f.id_gu.iloc[i]);gu=None if raw_gu is None else raw_gu.replace('성남시 ','') or None
            c.execute('INSERT OR IGNORE INTO grid_cell VALUES (?)',(gid,))
            existing=c.execute('SELECT id_gu FROM grid_feature WHERE ID_gid=?',(gid,)).fetchone()
            if existing and existing[0]!=raw_gu:raise ValueError('GRID_SCOPE_CHANGED')
            c.execute('INSERT OR IGNORE INTO grid_feature VALUES (?,?)',(gid,raw_gu))
            scored=pd.notna(out.score.iloc[i]);score=float(out.score.iloc[i]) if scored else None;rank=int(out.rank_no.iloc[i]) if scored else None
            val=lambda x:float(x.iloc[i]) if scored and pd.notna(x.iloc[i]) else None
            details={'stored':True,'raw_complaint_count':int(a.complaint_all.iloc[i]),'count_excl_low':int(a.complaint_lowexcluded.iloc[i]),'proxy_count':int(a.complaint_illustrative_filter.iloc[i]),'base_score':None if pd.isna(b.iloc[i]) else float(b.iloc[i]),'complaint_signal':val(s),'complaint_signal_points':val(term),'base_adjustment':val(adjustment),'cap_adjustment':val(cap),'net_change':score-float(b.iloc[i]) if scored else None,'rounding_adjustment':score-float(total.iloc[i]) if scored else None,'tie_size':int(out.tie_size.iloc[i]) if scored else None,'indicator_contributions':{k:None if pd.isna(v) else float(v) for k,v in contributions.iloc[i].items()},'observation_states':states.iloc[i].to_dict(),'classification_status':'OFFICIAL_INPUT_MISSING','reasons':['EXPERIMENTAL_PROXY_NOT_OFFICIAL']+([] if scored else ['OUTSIDE_COMMON_OBSERVED_POPULATION_OR_BASE_UNSCORED']),'manifest':manifest}
            obj={'run_id':run,'gid':gid,'gu':gu,'calculation_status':'EXPERIMENTAL' if scored else 'UNSCORED','official_score':None,'experimental_score':score,'experimental_rank':rank,'setting_version_id':sid,'setting_sha256':snapshot_hash,'rule_version':label,'input_sha256':hashes['grid'],'details':details}
            payload=canonical(obj)
            c.execute('INSERT INTO evidence VALUES (?,?,?,?,?)',(run,gid,gu,payload,digest(payload)))
            c.execute('INSERT INTO priority_candidate VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(run,gid,None,score,rank,details['raw_complaint_count'],details['count_excl_low'],None,None,None,None,None,obj['calculation_status']))
            if fail_after is not None and i+1==fail_after:raise RuntimeError('INJECTED_STORAGE_FAILURE')
    return {'run_id':run,'execution':'COMMITTED','rows':len(f),'scored':int(out.score.notna().sum()),'unscored':int(out.score.isna().sum()),'execution_fingerprint':fingerprint}

def read_result(database,run,gid):
    with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row
        r=c.execute('SELECT * FROM priority_run WHERE run_id=?',(run,)).fetchone()
        row=c.execute("SELECT p.*,NULLIF(REPLACE(f.id_gu,'성남시 ',''),'') gu FROM priority_candidate p JOIN grid_feature f ON p.gid=f.ID_gid WHERE run_id=? AND gid=?",(run,gid)).fetchone()
        if r is None or row is None:raise LookupError('RESULT_NOT_FOUND')
        ev=EvidenceStore(database).read(run,gid)
        st=c.execute('SELECT * FROM setting_version WHERE setting_version_id=?',(ev['setting_version_id'],)).fetchone()
        if st is None:raise ValueError('SETTING_MISSING')
        manifest=ev['details']['manifest']
        if r['note']!=manifest['execution_fingerprint']:raise ValueError('RUN_FINGERPRINT')
        return join_result(dict(r),dict(row),ev,dict(st),manifest)

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('execute')
    for name in ['grid','complaints','config','database']:e.add_argument('--'+name,required=True)
    r=sub.add_parser('read');r.add_argument('--database',required=True);r.add_argument('--run',type=int,required=True);r.add_argument('--gid',required=True)
    args=vars(p.parse_args());command=args.pop('command')
    print(canonical(execute(**args) if command=='execute' else read_result(**args)))
if __name__=='__main__':main()
