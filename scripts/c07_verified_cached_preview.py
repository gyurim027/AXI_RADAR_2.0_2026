"""Opt-in SE-02 verified C-07 CSV reuse. Read-only DB, no 59/62/77/78 writes.

The DB snapshot is read on every invocation to fingerprint *all C-07 input rows*.
Only the expensive build_contract work is skipped on a verified cache hit.
This does NOT claim that full source DB retrieval is eliminated.
Run a single instance per cache directory (verified_cache has no writer lock).
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import os
import tempfile

from app.core.db import read_only
from app.services.c07.rolling_contract import build_contract
from app.services.c07.verified_cache import Context, use_or_rebuild, sha256_file

SQL_GIDS = 'SELECT ID_gid FROM grid_feature ORDER BY ID_gid'
SQL_ROWS = ('SELECT complaint_id,gid,coord_accuracy,relevance,received_date,'
            'source_type,ped_type,report_type_raw FROM src_complaint ORDER BY complaint_id')
FIELDS = ('complaint_id','gid','coord_accuracy','relevance','received_date',
          'source_type','ped_type','report_type_raw')
PERIOD_START = '2021-01-01'
PERIOD_END = '2026-09-30'

def _normalize(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not (-float('inf') < value < float('inf')):
            raise ValueError('nonfinite source value')
        return value
    raise TypeError(f'unsupported source value: {type(value).__name__}')

def fingerprint(rows, gids):
    """Complete content digest of the columns consumed by current raw contract."""
    h = sha256()
    def put(value):
        h.update(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':'), allow_nan=False).encode('utf-8'))
        h.update(b'\n')
    put({'schema':'se02-source-projection-v1','sql':SQL_ROWS,'grid_sql':SQL_GIDS})
    for gid in gids:
        put(['gid', _normalize(gid)])
    for row in rows:
        put(['row', [_normalize(row.get(field)) for field in FIELDS]])
    return h.hexdigest()

def _atomic_text(path: Path, data: str):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.se02-',dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='ascii', newline='') as f:
            f.write(data)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def execute(*, cache_dir='out/se02_c07_verified_cache',
            start=PERIOD_START, end=PERIOD_END, source_reader=read_only,
            builder=build_contract):
    if start != PERIOD_START or end != PERIOD_END:
        raise ValueError('SE02_FIXED_PERIOD_ONLY; no period shortening')
    cache = Path(cache_dir)
    # Explicit opt-in; never overwrite legacy out/c07_full_source_*.csv/json.
    gids = [r['ID_gid'] for r in source_reader(SQL_GIDS)]
    rows = source_reader(SQL_ROWS)
    digest = fingerprint(rows, gids)
    # Only a SHA-256 digest of selected fields is persisted, not raw complaints.
    source_id = cache / '_source_projection.sha256'
    _atomic_text(source_id, digest + '\n')
    contract_source = Path(__import__('app.services.c07.rolling_contract', fromlist=['__file__']).__file__)
    this_script = Path(__file__)
    # Integrity identity is based on actual source projection, code contents, and policy fields.
    ctx = Context(start=start, end=end,
                  source_files=(str(source_id), str(contract_source), str(this_script)),
                  classification_version='raw-unconfirmed-no-review_status',
                  spatial_version='gid-from-src_complaint-and-grid_feature',
                  repeat_dedup_version='distinct_received_dates_per_gid_type',
                  location_quality_version='coord_accuracy-low-excluded',
                  algorithm_version='rolling_contract-code-content-verified',
                  extra_rules={'official_77_78_writes':'forbidden',
                               'reviewed_relevance':'not-confirmed-from-source'})
    def build_csv():
        result = builder(rows, gids, earliest=date.fromisoformat(start),
                         through=date.fromisoformat(end))
        if result['manifest']['period_start'] != start or result['manifest']['period_end'] != end:
            raise ValueError('C07_PERIOD_MISMATCH')
        if result['manifest']['source_row_count'] != len(rows) or result['manifest']['gid_count'] != len(gids):
            raise ValueError('C07_SOURCE_POPULATION_MISMATCH')
        buf = StringIO(newline='')
        columns = list(result['grids'][0])
        w = csv.DictWriter(buf, fieldnames=columns, lineterminator='\n')
        w.writeheader(); w.writerows(result['grids'])
        return ('\ufeff' + buf.getvalue()).encode('utf-8')
    result = use_or_rebuild(ctx, cache, build_csv)
    return {**result, 'source_projection_sha256': digest,
            'source_rows':len(rows), 'grid_count':len(gids),
            'period_start':start,'period_end':end,
            'read_only':True,'official_scoring_eligible':False,
            'source_db_fully_read':True}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir', default='out/se02_c07_verified_cache')
    args = p.parse_args()
    print(json.dumps(execute(cache_dir=args.cache_dir), ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
