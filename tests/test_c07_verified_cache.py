from dataclasses import replace
from pathlib import Path
import pytest
from app.services.c07.verified_cache import Context, CacheBlocked, use_or_rebuild


def ctx(tmp_path):
    source = tmp_path / 'raw.csv'
    source.write_bytes(b'id,month\n1,2026-01\n2,2026-02\n')
    return Context('2021-01-01','2026-09-30',(str(source),),'classification-v1',
                   'spatial-v1','repeat-cross-month-v1','quality-v1','code-v1')


def test_reuse_same_identity(tmp_path):
    c = ctx(tmp_path)
    calls = []
    def build():
        calls.append(1)
        return b'gid,complaints\nG1,2\n'
    a = use_or_rebuild(c, tmp_path/'cache', build)
    b = use_or_rebuild(c, tmp_path/'cache', build)
    assert not a['reused'] and b['reused'] and len(calls) == 1
    assert a['identity'] == b['identity']

@pytest.mark.parametrize('field', ['classification_version','spatial_version',
    'repeat_dedup_version','location_quality_version','algorithm_version','end'])
def test_change_invalidates(tmp_path,field):
    c = ctx(tmp_path)
    cache = tmp_path/'cache'
    use_or_rebuild(c,cache,lambda:b'gid,n\nG1,1\n')
    changed = replace(c, **{field:'2026-08-31' if field=='end' else 'new-version'})
    assert not use_or_rebuild(changed,cache,lambda:b'gid,n\nG1,2\n')['reused']

def test_source_add_modify_delete_invalidation(tmp_path):
    c = ctx(tmp_path)
    cache=tmp_path/'cache'
    use_or_rebuild(c,cache,lambda:b'gid,n\nG1,1\n')
    Path(c.source_files[0]).write_bytes(b'id,month\n2,2026-01\n')
    assert not use_or_rebuild(c,cache,lambda:b'gid,n\nG1,2\n')['reused']
    extra = tmp_path/'other.csv'; extra.write_bytes(b'hello')
    more = replace(c, source_files=c.source_files+(str(extra),))
    assert not use_or_rebuild(more,cache,lambda:b'gid,n\nG1,3\n')['reused']
    extra.unlink()
    with pytest.raises(FileNotFoundError):
        use_or_rebuild(more,cache,lambda:b'bad')

def test_output_tampering_blocks_reuse(tmp_path):
    c=ctx(tmp_path); cache=tmp_path/'cache'
    a=use_or_rebuild(c,cache,lambda:b'gid,n\nG1,1\n')
    Path(a['csv']).write_bytes(b'TAMPERED')
    b=use_or_rebuild(c,cache,lambda:b'gid,n\nG1,1\n')
    assert not b['reused']

def test_missing_version_blocks(tmp_path):
    c=replace(ctx(tmp_path),classification_version='')
    with pytest.raises(CacheBlocked,match='missing version'):
        use_or_rebuild(c,tmp_path/'cache',lambda:b'gid,n\nG1,1\n')

def test_mutation_during_build_blocks(tmp_path):
    c=ctx(tmp_path)
    def build():
        Path(c.source_files[0]).write_bytes(b'changed')
        return b'gid,n\nG1,1\n'
    with pytest.raises(CacheBlocked,match='during full aggregation'):
        use_or_rebuild(c,tmp_path/'cache',build)

def test_cross_month_repeat_policy_change_rebuilds_full(tmp_path):
    c=ctx(tmp_path)
    calls=[]
    def full():
        calls.append('full')
        return b'gid,n\nG1,1\n'
    use_or_rebuild(c,tmp_path/'cache',full)
    use_or_rebuild(replace(c,repeat_dedup_version='crossmonth-v2'),tmp_path/'cache',full)
    assert calls == ['full','full']
