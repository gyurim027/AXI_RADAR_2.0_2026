"""B05: actual A/B/C consumer, gated by B04 classification contract.
No source writes, no approval mutation, no 77/78 writes.
"""
from __future__ import annotations
from pathlib import Path
import csv, json
from app.services.scoring.mode_comparison import compare_all_modes, MODES

class B05Blocked(ValueError):
    pass

def inspect_b04(manifest: dict, rows: list[dict]):
    if manifest.get('B04') not in (None,'C07_EXISTING_SCORING_CONSUMER_CONNECTED'):
        raise B05Blocked('UNEXPECTED_B04_SOURCE')
    grids = manifest.get('grid_count', manifest.get('grids'))
    confirmed_value = manifest.get('human_confirmed', manifest.get('confirmed'))
    unconfirmed_value = manifest.get('unconfirmed')
    if grids is None or confirmed_value is None or unconfirmed_value is None:
        raise B05Blocked('B04_REQUIRED_MANIFEST_FIELDS_MISSING')
    if len(rows) != int(grids):
        raise B05Blocked('B04_GRID_COUNT_MISMATCH')
    if len({r['gid'] for r in rows}) != len(rows):
        raise B05Blocked('B04_DUPLICATE_GIDS')
    confirmed=int(confirmed_value); unconfirmed=int(unconfirmed_value)
    if min(confirmed,unconfirmed)<0 or (manifest.get('source_rows') is not None and confirmed+unconfirmed!=int(manifest['source_rows'])):
        # This run's observed C07 source size; do not make a global assumption about future runs.
        raise B05Blocked('B04_REVIEW_TOTAL_MISMATCH')
    blockers=list(manifest.get('blockers', []))
    eligible=bool(manifest.get('scoring_ready') is True and unconfirmed==0 and not blockers and confirmed>0)
    if any(r.get('classification_status')!='COMPLETE' for r in rows):eligible=False
    return {'eligible':eligible,'confirmed':confirmed,'unconfirmed':unconfirmed,'grids':len(rows),
            'blockers':sorted(set(blockers + ([] if eligible else ['B04_SOURCE_NOT_SCORING_READY'])))}

def run_b05(*, b04_manifest:dict, b04_rows:list[dict], grid_rows=None, reviewed_rows=None,
            start=None,end=None,policy_document=None,top_n=35)->dict:
    gate=inspect_b04(b04_manifest,b04_rows)
    output={'B05':'ABC_THREE_MODES_CONSUMER','status':'BLOCKED_UPSTREAM' if not gate['eligible'] else 'READY_FOR_COMPARISON',
            'modes':list(MODES),'mode_labels':{'independent':'A','inside_hazard':'B','bonus':'C'},
            'b04_gate':gate,'official_allowed':False,'db_writes':0,'official_77_78_writes':0}
    if not gate['eligible']:
        return output
    if any(item is None for item in (grid_rows,reviewed_rows,start,end,policy_document)):
        output['status']='BLOCKED_MISSING_ACTUAL_SCORING_INPUTS'
        output['b04_gate']['blockers'].append('GRID_REVIEWED_DATE_POLICY_REQUIRED')
        return output
    if len(grid_rows)!=gate['grids'] or {str(r['ID_gid']) for r in grid_rows}!={r['gid'] for r in b04_rows}:
        raise B05Blocked('GRID_INPUT_MISMATCH')
    if not reviewed_rows:raise B05Blocked('HUMAN_REVIEWED_ROWS_REQUIRED')
    result=compare_all_modes(grid_rows=grid_rows,reviewed_rows=reviewed_rows,start=start,end=end,
                             policy_document=policy_document,top_n=top_n)
    output.update(status='COMPARED_READ_ONLY',comparison=result)
    return output

def from_b04_files(csv_path,manifest_path,**kwargs):
    with Path(csv_path).open('r',encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    return run_b05(b04_manifest=manifest,b04_rows=rows,**kwargs)
