"""Read actual 79 + 05 in one DB session and export C-07 monthly contract. No writes."""
import argparse
import csv
import json
from datetime import date
from pathlib import Path
from app.core.db import read_only
from app.services.c07.rolling_contract import build_contract


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out', default='out/c07_full_source')
    parser.add_argument('--through', help='YYYY-MM-DD; default latest actual 79 received_date')
    parser.add_argument('--verified-cache', action='store_true',
                        help='Use verified, read-only C-07 aggregate preview cache')
    opts=parser.parse_args()
    if opts.verified_cache:
        if opts.out != 'out/c07_full_source':
            parser.error('--out cannot be combined with --verified-cache')
        if opts.through not in (None, '2026-09-30'):
            parser.error('--verified-cache currently supports only through=2026-09-30')
        import subprocess
        import sys
        subprocess.run(
            [sys.executable, '-m', 'scripts.c07_verified_cached_preview'],
            check=True
        )
        return
    # No assumption about an unimplemented C-08 SQL table: source-only data here.
    gids=[r['ID_gid'] for r in read_only('SELECT ID_gid FROM grid_feature ORDER BY ID_gid')]
    rows=read_only('SELECT complaint_id,gid,coord_accuracy,relevance,received_date,source_type,ped_type,report_type_raw '
                   'FROM src_complaint ORDER BY complaint_id')
    result=build_contract(rows,gids, earliest=date(2021,1,1),
                          through=date.fromisoformat(opts.through) if opts.through else None)
    out=Path(opts.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=list(result['grids'][0])
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(result['grids'])
    out.with_suffix('.json').write_text(json.dumps(result['manifest'],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output_csv':str(out.with_suffix('.csv')),
                      'output_manifest':str(out.with_suffix('.json')),
                      'period_end':result['manifest']['period_end'],
                      'records':result['manifest']['scoped_row_count'],
                      'grid_count':len(result['grids']),
                      'read_only':True},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
