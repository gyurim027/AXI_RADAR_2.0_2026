from dataclasses import replace
import pytest
from app.services.scoring.production_writer import OfficialBatch,ProductionBlocked,plan,inspect_dependencies

from datetime import date
from app.services.scoring.setting_links import KINDS, SettingReference
D='a'*64
REFS=tuple(SettingReference(i,k,'sha256:'+D,'v1',None) for i,k in zip((2,3,4),KINDS))
LINKED=[dict(setting_version_id=r.setting_version_id,setting_kind=r.setting_kind,content_ref=r.content_ref,version_label=r.version_label,version_no=None,approval_status='승인',approved_at='MOCK_ONLY') for r in REFS]
R={'gid':'GRID1','calculation_status':'OFFICIAL','official_score':'15.4321',
   'rank_no':1,'input_status':'VERIFIED_CLASSIFIED','classification_status':'COMPLETE',
   'source_kind':'CLASSIFIED','complaint_cnt':2,'complaint_cnt_excl_low':1,'selected_yn':None}
B=OfficialBatch('verified-build','v1',2,'sha256:'+D,D,D,D,(R,), 'owner','approval-123',REFS,date(2021,1,1),date(2026,9,30))

def test_plan_no_write():
    assert plan(B)['status']=='VALIDATED_NOT_WRITTEN'

def test_exploratory_rejected():
    for change in ({'source_kind':'EXPLORATORY_PROXY'},{'calculation_status':'EXPERIMENTAL'},
                   {'classification_status':'OFFICIAL_INPUT_MISSING'},{'official_score':None}):
        with pytest.raises(ProductionBlocked):plan(replace(B,candidates=({**R,**change},)))

def test_duplicated_grid_rejected():
    with pytest.raises(ProductionBlocked):plan(replace(B,candidates=(R,R)))

def test_missing_setting_blocks():
    with pytest.raises(ProductionBlocked,match='SETTING_NOT_FOUND'):
        inspect_dependencies(lambda sql,args: [],B)

def test_unapproved_setting_blocks():
    def read(sql,args):
        if ' IN (' in sql:return LINKED
        return [{'content_ref':'sha256:'+D,'approval_status':'제안', 'version_label':'v1','approved_at':None}]
    with pytest.raises(ProductionBlocked,match='SETTING_NOT_APPROVED'):
        inspect_dependencies(read,B)

def test_approved_setting_and_grid_checked():
    def read(sql,args):
        if ' IN (' in sql:return LINKED
        if 'FROM setting_version' in sql:
            return [{'content_ref':'sha256:'+D,'approval_status':'승인', 'version_label':'v1','approved_at':'2026-10-25'}]
        if 'COUNT(' in sql:return [{'n':2406}]
        return [{'ID_gid':'GRID1'}]
    assert inspect_dependencies(read,B)['status']=='DEPENDENCIES_CHECKED_NOT_WRITTEN'
