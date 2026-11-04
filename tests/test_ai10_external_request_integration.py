"""Standalone integration check: no database or LLM call."""
import importlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

module = importlib.import_module('app.services.ai10.ai10_case_draft')

base = dict(
    approved_case_token='SAFE_TEST_01',
    reviewed_findings=[{'source_id': 'SRC06', 'finding_type': 'assessment_requires_review', 'evidence_state': 'assessment_result'}],
    allowed_src_ids={'SRC06'},
    source_access={'SRC06': '공개'},
)
request = module.prepare_external_llm_request(**base)
assert request['data_ids'] == ['SRC06']
assert request['contains_raw'] is False
assert request['llm_called'] is False
assert request['schema'] is module.CaseDraftOutput
prompt = request['messages'][0]['content']
assert 'SAFE_TEST_01' in prompt
for forbidden in ('raw_value', 'facility_id', 'record_reference', 'gid', 'claim_or_finding', 'issue_description', 'source_table'):
    assert forbidden not in prompt, forbidden
assert json.loads(prompt.split('CASE_JSON: ', 1)[1])['findings'][0]['source_id'] == 'SRC06'
print('PASS: generator module builds sanitized request; no LLM called')

for name, bad in [
    ('internal SRC', {**base, 'source_access': {'SRC06': '공개 (팀 내부)'}}),
    ('unapproved SRC', {**base, 'allowed_src_ids': set()}),
    ('unsafe finding', {**base, 'reviewed_findings': [{**base['reviewed_findings'][0], 'raw_value': 'secret'}]}),
]:
    try:
        module.prepare_external_llm_request(**bad)
    except ValueError:
        print('PASS:', name, 'blocked')
    else:
        raise AssertionError(f'{name} should be blocked')
print('RESULT: PASS (request preparation only; no database / LLM call)')
