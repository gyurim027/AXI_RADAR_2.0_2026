"""Read persisted verified results. Scenario comparison, never half-year change."""
import argparse,json,sqlite3
from pathlib import Path
import pandas as pd
from .runtime import read_result

def export_analysis(database,runs,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);frames=[];contracts=[]
    for run in runs:
        with sqlite3.connect(database) as c:gids=[r[0] for r in c.execute('SELECT gid FROM priority_candidate WHERE run_id=?',(run,))]
        if not gids:raise ValueError('RUN_NOT_FOUND')
        records=[]
        for gid in gids:
            obj=read_result(database,run,gid);d=obj['details'];m=d['manifest']
            records.append({'run_id':run,'gid':gid,'gu':obj['gu'],'score':obj['experimental_score'],'rank':obj['experimental_rank'],'tie_size':d['tie_size'],'status':obj['calculation_status'],'base_score':d['base_score'],'complaint_points':d['complaint_signal_points'],'net_change':d['net_change']})
        contracts.append({'run_id':run,'inputs':m['inputs'],'config':m['policies'][0]})
        frames.append(pd.DataFrame(records))
    f=pd.concat(frames);f.to_csv(out/'grid_analysis.csv',index=False)
    f.groupby(['run_id','gu'],dropna=False).agg(rows=('gid','size'),scored=('score','count'),mean_score=('score','mean'),max_score=('score','max')).to_csv(out/'district_analysis.csv')
    f.groupby(['run_id','status']).size().to_csv(out/'status_analysis.csv')
    same=all(x['inputs']==contracts[0]['inputs'] for x in contracts)
    for x in contracts[1:]:
        a=frames[0].set_index('gid');b=f[f.run_id==x['run_id']].set_index('gid')
        keys=['fit_population','comparison_population','period_note']
        if not same or any(x['config'][k]!=contracts[0]['config'][k] for k in keys) or set(a.index)!=set(b.index):raise ValueError('INCOMPARABLE_RUNS')
        b=b.loc[a.index];delta=pd.DataFrame({'score_delta':b.score-a.score,'rank_delta':b['rank']-a['rank']});delta.to_csv(out/f'delta_{runs[0]}_{x["run_id"]}.csv')
    (out/'comparison_contract.json').write_text(json.dumps({'kind':'SCENARIO_NOT_HALF_YEAR','official':False,'contracts':contracts},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--runs',nargs='+',type=int,required=True);p.add_argument('--out',required=True);export_analysis(**vars(p.parse_args()))
