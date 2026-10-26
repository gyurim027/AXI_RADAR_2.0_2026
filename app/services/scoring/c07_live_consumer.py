"""B04: Consume B03 C08->C07 output in the *existing* scoring input validator.

No guessed labels; zero reviewed rows are not zero relevant complaints.
Never approves 62, changes source, or writes 77/78.
"""
from __future__ import annotations
import pandas as pd
from app.services.scoring.calculation import validate_complaint_input

class C07ConsumptionBlocked(ValueError):
    pass


def consume_c07_contract(contract: dict) -> dict:
    """Map B03 live contract to scoring's exact columns; validate with real validator."""
    manifest = contract['manifest']
    grid_rows = contract['grids']
    if not grid_rows or len(grid_rows) != manifest['gid_count']:
        raise C07ConsumptionBlocked('GRID_POPULATION_MISMATCH')
    source_total = int(manifest['scoped_row_count'])
    confirmed = int(manifest['human_confirmed_rows'])
    unconfirmed = int(manifest['unconfirmed_rows'])
    if confirmed < 0 or unconfirmed < 0 or confirmed + unconfirmed != manifest['source_row_count']:
        raise C07ConsumptionBlocked('SOURCE_REVIEW_PARTITION_MISMATCH')
    # Scope must never be mistaken for a fully confirmed national/source population.
    full = (unconfirmed == 0 and confirmed > 0 and
            manifest.get('source_population_complete') is True and
            manifest.get('c07_for_official_score_allowed') is True)
    data=[]
    for r in grid_rows:
        raw=int(r['complaint_cnt'])
        rv=int(r['reviewed_count'])
        unknown=int(r['unreviewed_count'])
        relevant=int(r['reviewed_relevant_count'])
        quality=int(r['reviewed_relevant_excl_low'])
        if min(raw,rv,unknown,relevant,quality) < 0 or rv+unknown!=raw or quality>relevant or relevant>rv:
            raise C07ConsumptionBlocked('GRID_COUNT_CONTRADICTION:'+str(r['gid']))
        if (unknown == 0) != (r['classification_status']=='COMPLETE'):
            raise C07ConsumptionBlocked('GRID_REVIEW_STATUS_CONTRADICTION:'+str(r['gid']))
        data.append({'gid':str(r['gid']), 'relevant_count':relevant,
                     'repeat_count':int(r['repeat_relevant_count']) if full else None,
                     'count_excl_low':quality,
                     'classification_status':r['classification_status']})
    if sum(int(r['complaint_cnt']) for r in grid_rows)>source_total:
        raise C07ConsumptionBlocked('GRID_SOURCE_EXCEEDS_SCOPE')
    frame=pd.DataFrame(data)
    # No invented approval of dedup, quality, vocabulary, or snapshot controls.
    # They remain missing until their respective authoritative evidence is supplied.
    meta={'period_start':manifest['period_start'],'period_end':manifest['period_end'],
          'source_snapshot':manifest['sha256'], 'coverage_verified':False,
          'classification_version':'C08_HUMAN_REVIEW',
          'aggregation_version':'C07_B03_BRIDGE',
          'dedup_policy':None,'location_policy':None,'ped_type_vocabulary':None,
          'relevance_policy':None,'confidence_policy':None,'repeat_policy':None}
    errors=validate_complaint_input(frame,meta,frame.gid.tolist())
    if unconfirmed: errors=sorted(set(errors+['SOURCE_CLASSIFICATION_PENDING']))
    if not full: errors=sorted(set(errors+['SOURCE_COVERAGE_NOT_CONFIRMED']))
    return {'status':'BLOCKED' if errors else 'READY',
            'scoring_consumer':'app.services.scoring.calculation.validate_complaint_input',
            'scoring_ready':not errors, 'official_write_allowed':False,
            'source_rows':manifest['source_row_count'],
            'period_rows':source_total,'human_confirmed':confirmed,
            'unconfirmed':unconfirmed,'grid_count':len(frame),
            'blockers':errors,'metadata':meta,'rows':frame.to_dict('records')}


def consume_live_c08(*,start=None,end=None):
    from app.services.c07.human_decision_bridge import c07_from_live_c08
    kwargs={}
    if start is not None:kwargs['start']=start
    if end is not None:kwargs['end']=end
    return consume_c07_contract(c07_from_live_c08(**kwargs))
