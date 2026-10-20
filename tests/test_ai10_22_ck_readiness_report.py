"""원본 22건의 현재 정보만으로 판정하는 것을 차단하는 회귀시험."""
import json
from pathlib import Path
from ai10_22_ck_readiness_report import report
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'data'/'RADAR_AI10_민원샘플_정리_v2.json').read_text(encoding='utf-8-sig'))['records']
rules=json.loads((ROOT/'data'/'ai10_ck_rules_v0.4.1.json').read_text(encoding='utf-8-sig'))['rules']
r=report(records,rules)
assert r['counts']['all']==22
assert r['counts']['provisional_ck']==3
assert r['counts']['ck_missing']==19
assert r['counts']['ck_applied']==0
assert len({x['sample_id'] for x in r['records']})==22
assert all(not x['ck_applied'] and not x['gemini_invoked'] and not x['operator_approved'] for x in r['records'])
assert all(x['required_next_input'] and x['reason'] for x in r['records'])
assert all(x['ck_provisional']=='CK-14' for x in r['records'] if x['ck_provisional'])
assert r['counts']['scope']=={'적합':3,'비대상':7,'조건부':5,'검토 전':7},r['counts']['scope']
assert all(x['sample_scope']=='적합' for x in r['records'] if x['ck_provisional'])
print('22건 CK 적용 준비 상태 검사: 10/10 통과 | Gemini/DB 호출 없음')
