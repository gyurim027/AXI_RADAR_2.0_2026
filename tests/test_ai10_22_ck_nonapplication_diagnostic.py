"""22건 CK 미적용 원인 진단: Gemini 호출 없이 현재 입력 구조 재검증."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_ai10_complaint_latest_compare_v052 import read, build
samples = read(ROOT / 'data' / 'RADAR_AI10_민원샘플_정리_v2.json')['records']
rules = {x['rule_id']: x for x in read(ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json')['rules']}
rows = build(samples, rules, generate=False)
assert len(rows) == 22, f'샘플 수 이상: {len(rows)}'
assert len({x['sample_id'] for x in rows}) == 22, '샘플 ID 중복'
assert sum(x['ck_link_diagnostic']['stage'] == 'CK 입력 이전' for x in rows) == 19
assert sum(x['ck_link_diagnostic']['stage'] == 'CK 잠정 후보 대조' for x in rows) == 3
assert all(x['ck_link_diagnostic']['gemini_attempted'] is False for x in rows)
assert all(x['ck_link_diagnostic']['ck_applied'] is False for x in rows)
assert all(x['operator_approved'] is False and x['final_candidate_proposal'] is None for x in rows)
assert all('ck_link_diagnostic' in x for x in rows)
print('22건 진단: 22/22 PASS | 후보 미입력 19 · 잠정 후보 3 | Gemini/DB 호출 없음')
