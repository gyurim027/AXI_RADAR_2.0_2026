"""Unit test without global pytest fixtures, DB or LLM: run as a plain Python script."""
from pathlib import Path
import importlib.util

root = Path(__file__).resolve().parents[1]
path = root / 'app/services/ai10/ai10_external_payload.py'
spec = importlib.util.spec_from_file_location('ai10_external_payload', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

base = dict(approved_case_token='SAFE-1', reviewed_findings=[dict(source_id='SRC06', finding_type='assessment_requires_review', evidence_state='assessment_result')], allowed_src_ids={'SRC06'}, source_access={'SRC06':'공개'})
proj=module.make_external_projection(**base)
assert proj['data_ids']==['SRC06']
s=module.render_external_case_json(**base)
assert all(x not in s for x in ('raw_value','claim_or_finding','facility_id','gid','record_reference','issue_description'))
print('PASS: strictly structured projection')

for name, update in {
 'raw_field':{'reviewed_findings':[dict(base['reviewed_findings'][0],raw_value='PRIVATE')]},
 'unapproved':{'allowed_src_ids':set()},
 'internal':{'source_access':{'SRC06':'공개 (팀 내부)'}},
 'free_text':{'reviewed_findings':[dict(source_id='SRC06',finding_type='자유입력',evidence_state='assessment_result')]},
 'bad_token':{'approved_case_token':'37.123 127.123'},
}.items():
    try:
        module.make_external_projection(**(base | update))
    except ValueError:
        print('PASS: blocked '+name)
    else:
        raise AssertionError(name+' was not blocked')
print('RESULT: PASS (projection only; no LLM or DB called)')
