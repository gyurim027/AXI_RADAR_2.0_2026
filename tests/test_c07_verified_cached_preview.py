"""Offline SE-02 integration contract checks; no DB connection."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import pytest
from scripts.c07_verified_cached_preview import execute, fingerprint, SQL_GIDS, SQL_ROWS

ROWS = [{'complaint_id':'1','gid':'g1','coord_accuracy':'높음','relevance':'Y',
         'received_date':date(2023,2,2),'source_type':'S','ped_type':'p','report_type_raw':'raw'}]

def fake_reader_factory(data):
    def read(sql):
        if sql == SQL_GIDS: return [{'ID_gid':'g1'}]
        if sql == SQL_ROWS: return [dict(row) for row in data]
        raise AssertionError(sql)
    return read

def test_same_input_uses_cache_and_skips_builder(tmp_path):
    calls=[]
    def builder(rows, gids, *, earliest, through):
        calls.append(1)
        return {'manifest':{'period_start':str(earliest),'period_end':str(through),
                            'source_row_count':len(rows),'gid_count':len(gids)},
                'grids':[{'gid':'g1','complaint_cnt':1}]}
    a=execute(cache_dir=tmp_path,source_reader=fake_reader_factory(ROWS),builder=builder)
    b=execute(cache_dir=tmp_path,source_reader=fake_reader_factory(ROWS),builder=builder)
    assert not a['reused'] and b['reused'] and len(calls)==1
    assert Path(b['csv']).exists()
    assert b['official_scoring_eligible'] is False

def test_content_change_forces_full_builder(tmp_path):
    calls=[]
    def builder(rows, gids, *, earliest, through):
        calls.append(1)
        return {'manifest':{'period_start':str(earliest),'period_end':str(through),
                            'source_row_count':len(rows),'gid_count':len(gids)},
                'grids':[{'gid':'g1','complaint_cnt':1}]}
    execute(cache_dir=tmp_path,source_reader=fake_reader_factory(ROWS),builder=builder)
    new=[dict(ROWS[0],relevance='N')]
    c=execute(cache_dir=tmp_path,source_reader=fake_reader_factory(new),builder=builder)
    assert not c['reused'] and len(calls)==2

def test_ped_type_change_forces_rebuild(tmp_path):
    def build(rows,gids,*,earliest,through):
        return {'manifest':{'period_start':str(earliest),'period_end':str(through),
                            'source_row_count':len(rows),'gid_count':len(gids)},
                'grids':[{'gid':'g1','complaint_cnt':1}]}
    execute(cache_dir=tmp_path,source_reader=fake_reader_factory(ROWS),builder=build)
    assert execute(cache_dir=tmp_path,source_reader=fake_reader_factory([dict(ROWS[0],ped_type='q')]),builder=build)['reused'] is False

def test_no_period_shorten(tmp_path):
    with pytest.raises(ValueError,match='FIXED_PERIOD'):
        execute(cache_dir=tmp_path,start='2023-01-01',source_reader=lambda _:[])

def test_content_hash_changes_on_same_row_count():
    assert fingerprint(ROWS,['g1']) != fingerprint([dict(ROWS[0],gid='g2')],['g1'])

def test_legacy_not_reused(tmp_path):
    (tmp_path/'c07_full_source_2021_to_latest.csv').write_text('existing but unverified')
    def build(rows,gids,*,earliest,through):
        return {'manifest':{'period_start':str(earliest),'period_end':str(through),
                            'source_row_count':len(rows),'gid_count':len(gids)},
                'grids':[{'gid':'g1','complaint_cnt':1}]}
    assert not execute(cache_dir=tmp_path,source_reader=fake_reader_factory(ROWS),builder=build)['reused']
