"""Experimental scoring components. No approved policy or production writer.
All policy choices must be supplied explicitly. C-07 remains upstream owner.
"""
from dataclasses import dataclass, asdict
import hashlib,json
import numpy as np
import pandas as pd

FEATURES = ['res_fatal_accident_cnt','res_hotspot_cnt','res_ped_hotspot_cnt','cond_blind_spot_cnt','cond_obstacle_cnt','exp_board_alight_daily_avg','vul_zone_total','cond_pothole_detect_cnt','cond_delineator_detect_cnt']
DOMAINS = {'accident':FEATURES[:3], 'hazard':[FEATURES[i] for i in [3,4,7,8]], 'exposure':[FEATURES[5]], 'vulnerability':[FEATURES[6]]}

@dataclass(frozen=True)
class Policy:
    label: str
    normalization: str
    observation: str
    domain_weights: dict
    accident_reduce: str
    missing: str
    def validate(self):
        if self.normalization not in {'positive_upper','positive_mid','log_max','q95_cap'}: raise ValueError('normalization')
        if self.observation not in {'record_zero_counterfactual','scope_aware'}: raise ValueError('observation')
        if self.accident_reduce not in {'mean','max'}: raise ValueError('accident_reduce')
        if self.missing not in {'renormalize','strict'}: raise ValueError('missing')
        if set(self.domain_weights)!=set(DOMAINS): raise ValueError('domains')
        w=np.array(list(self.domain_weights.values()),dtype=float)
        if not np.isfinite(w).all() or (w<=0).any() or not np.isclose(w.sum(),1): raise ValueError('weights')
    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

def normalize(values, method):
    if method not in {'positive_upper','positive_mid','log_max','q95_cap'}: raise ValueError('normalization')
    x=pd.Series(values,dtype=float)
    if np.isinf(x).any() or x.dropna().lt(0).any(): raise ValueError('negative/nonfinite input')
    p=x[x>0]; y=pd.Series(np.nan,index=x.index); y.loc[x.eq(0)]=0
    if p.empty: return y
    if method=='positive_upper': y.loc[p.index]=p.rank(method='max',pct=True)
    elif method=='positive_mid': y.loc[p.index]=p.rank(method='average',pct=True)
    elif method=='log_max': y=np.log1p(x)/np.log1p(p.max())
    elif method=='q95_cap': y=(x/p.quantile(.95)).clip(upper=1)
    else: raise ValueError('normalization')
    return y

def rank_scores(scores,gids):
    # Rank after DB precision rounding. gid determines display order only.
    frame=pd.DataFrame({'gid':list(gids),'score':pd.Series(scores).to_numpy()})
    frame['score']=frame.score.round(4)
    frame['rank_no']=frame.score.rank(method='min',ascending=False).astype('Int64')
    frame['tie_size']=frame.groupby('score',dropna=True).score.transform('size').astype('Int64')
    order=frame.sort_values(['score','gid'],ascending=[False,True],na_position='last')
    frame['display_order']=pd.Series(range(1,len(order)+1),index=order.index)
    return frame

def calculate(frame, policy):
    policy.validate()
    if frame.ID_gid.isna().any() or not frame.ID_gid.is_unique: raise ValueError('invalid grid keys')
    x=frame[FEATURES].apply(pd.to_numeric,errors='raise').astype(float)
    states=pd.DataFrame('RECORD_VALUE',index=x.index,columns=x.columns)
    if policy.observation=='scope_aware':
        mask=~frame.ext_survey_scope_obstacle.eq('Y')
        x.loc[mask,FEATURES[4]]=np.nan;states.loc[mask,FEATURES[4]]='OUTSIDE_SURVEY_SCOPE'
        for c in [FEATURES[3],FEATURES[7],FEATURES[8]]:
            mask=x[c].eq(0);x.loc[mask,c]=np.nan;states.loc[mask,c]='NO_RECORD_COVERAGE_UNKNOWN'
    states=states.mask(x.isna() & states.eq('RECORD_VALUE'),'MISSING_INPUT')
    norm=pd.DataFrame({c:normalize(x[c],policy.normalization) for c in FEATURES})
    domains=pd.DataFrame(index=x.index); contribution=pd.DataFrame(0.,index=x.index,columns=FEATURES)
    for domain,cols in DOMAINS.items():
        block=norm[cols]
        if domain=='accident' and policy.accident_reduce=='max': domains[domain]=block.max(axis=1)
        else: domains[domain]=block.mean(axis=1)
        if policy.missing=='strict': domains.loc[block.isna().any(axis=1),domain]=np.nan
    weights=pd.Series(policy.domain_weights)
    denominator=domains.notna().mul(weights).sum(axis=1)
    score=domains.mul(weights).sum(axis=1,min_count=1).div(denominator.where(denominator.gt(0)))*100
    if policy.missing=='strict': score=score.where(norm.notna().all(axis=1))
    for domain,cols in DOMAINS.items():
        b=norm[cols]
        if domain=='accident' and policy.accident_reduce=='max':
            winners=b.eq(b.max(axis=1),axis=0)&b.notna(); part=b.where(winners,0).div(winners.sum(axis=1).replace(0,np.nan),axis=0)
        else: part=b.div(b.notna().sum(axis=1).replace(0,np.nan),axis=0)
        contribution[cols]=part.mul(weights[domain]).div(denominator,axis=0)*100
    contribution=contribution.where(score.notna(),np.nan)
    assert np.allclose(contribution.sum(axis=1,min_count=1),score,equal_nan=True)
    ranked=rank_scores(score,frame.ID_gid)
    ranked['gu']=frame.id_gu.values
    ranked['observed_indicator_count']=norm.notna().sum(axis=1).values
    ranked['coverage_fraction']=norm.notna().mean(axis=1).values
    ranked['status']=np.where(score.notna(),'EXPERIMENTAL','UNSCORED')
    return ranked,domains,contribution,states

# Proposed engine-side consumer contract, not C-07 implementation.
CONTRACT_META=['classification_version','aggregation_version','source_snapshot','period_start','period_end','dedup_policy','location_policy','ped_type_vocabulary','relevance_policy','confidence_policy','repeat_policy','coverage_verified']
def validate_complaint_input(rows, meta, gids):
    errors=[]
    for k in CONTRACT_META:
        if k not in meta or meta[k] is None or meta[k]=='': errors.append('missing_metadata:'+k)
    if meta.get('coverage_verified') is not True: errors.append('coverage_unverified')
    start=pd.to_datetime(meta.get('period_start'),errors='coerce');end=pd.to_datetime(meta.get('period_end'),errors='coerce')
    if pd.isna(start) or pd.isna(end) or start>end: errors.append('invalid_period')
    needed=['gid','relevant_count','repeat_count','count_excl_low','classification_status']
    if not set(needed)<=set(rows.columns):return sorted(set(errors+['missing_columns']))
    if rows.gid.isna().any() or rows.gid.duplicated().any():errors.append('invalid_grid_key')
    if set(rows.gid)!=set(gids):errors.append('grid_population_mismatch')
    if not rows.classification_status.eq('COMPLETE').all():errors.append('classification_incomplete')
    for c in needed[1:4]:
        x=pd.to_numeric(rows[c],errors='coerce')
        if x.isna().any() or not np.isfinite(x).all() or x.lt(0).any() or x.mod(1).ne(0).any():errors.append('invalid_count:'+c)
    if not any(x.startswith('invalid_count') for x in errors):
        for c in ['repeat_count','count_excl_low']:
            if (pd.to_numeric(rows[c])>pd.to_numeric(rows.relevant_count)).any():errors.append('count_exceeds_relevant:'+c)
    return sorted(set(errors))

def combine_complaint(base, domains, signal, *, mode, strength, hazard_weight):
    if not 0<=strength<=1 or not 0<hazard_weight<=1:raise ValueError('invalid strength')
    b=pd.Series(base,dtype=float);s=pd.Series(signal,dtype=float)
    if len(b)!=len(s) or not b.index.equals(s.index):raise ValueError('unaligned input')
    if np.isinf(b).any() or np.isinf(s).any() or not b.dropna().between(0,100).all(): raise ValueError('invalid base/signal')
    if (s.dropna().lt(0)|s.dropna().gt(1)).any():raise ValueError('signal outside [0,1]')
    if mode=='independent':total=(1-strength)*b+strength*100*s
    elif mode=='inside_hazard':total=b+hazard_weight*strength*(100*s-100*domains['hazard'])
    elif mode=='bonus':total=(b+100*strength*s).clip(upper=100)
    else:raise ValueError('unknown mode')
    total=total.where(b.notna()&s.notna())
    return total,total-b

def official_export_guard(*,policy_approved,complaint_errors):
    if not policy_approved or complaint_errors:raise ValueError('OFFICIAL_EXPORT_BLOCKED')
