"""Gemini API 미호출: 두 응답을 모의하여 재생성 및 차단 규칙 검증."""
import importlib.util, json, os, sys, tempfile, types
import pytest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json').is_file():
    pytest.skip('AI-10 CK 규칙 파일 미배치', allow_module_level=True)
if not (ROOT / 'data' / 'ai10_reference' / 'seongnam_mobility_plan_excerpt_2026.json').is_file():
    pytest.skip('AI-10 추가 참고자료 JSON 미배치', allow_module_level=True)
FILE = ROOT / 'app' / 'services' / 'AI-10' / 'ai10_draft.py'
spec=importlib.util.spec_from_file_location('draft_retry',FILE)
m=importlib.util.module_from_spec(spec)
sys.modules['draft_retry']=m
spec.loader.exec_module(m)
m.RULES_PATH = ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json'

bad={'rule_id':'CK-03','draft_template':'점자블록 시설 자료가 없거나 과거 기록입니다. 점자블록 설치를 요청하시기 바랍니다.','review_note':'시험'}
good={'rule_id':'CK-03','draft_template':'현재 확보된 자료만으로는 점자블록의 현재 상태를 확인할 수 없습니다. 현장 설치 여부와 연속성을 확인한 후 필요한 조치를 검토해 주세요.','review_note':'근거 원문 직접 확인 필요'}
assert '현재 확보한 자료만으로' in m.make_prompt(m.load_rule('CK-03'))
print('PASS | 미확정 데이터에 안전한 표현 안내')
try:m.validate_draft(m.DraftOutput(**bad),'CK-03')
except ValueError: print('PASS | 문제가 있는 문장 차단')
else:raise AssertionError('잘못된 문장 통과')
assert m.validate_draft(m.DraftOutput(**good),'CK-03').rule_id=='CK-03'
print('PASS | 안전한 두 문장 허용')

class FakeClient:
    replies=[]
    calls=0
    def __init__(self,**kwargs):self.models=self
    def generate_content(self,**kwargs):
        FakeClient.calls+=1
        return types.SimpleNamespace(text=json.dumps(FakeClient.replies.pop(0),ensure_ascii=False))
    def close(self):pass
fakegenai=types.ModuleType('google.genai');fakegenai.Client=FakeClient
faketypes=types.SimpleNamespace(GenerateContentConfig=lambda **kw:kw)
fakedotenv=types.SimpleNamespace(load_dotenv=lambda *a,**kw:None)
fakegenai.types=faketypes
fakegoogle=types.ModuleType('google');fakegoogle.genai=fakegenai
with patch.dict(sys.modules,{'google':fakegoogle,'google.genai':fakegenai,'google.genai.types':faketypes,'dotenv':fakedotenv}),patch.dict(os.environ,{'GEMINI_API_KEY':'unit-test','GEMINI_MODEL':'mock'}):
    FakeClient.replies=[bad.copy(),good.copy()];FakeClient.calls=0
    assert m.generate_draft('CK-03').draft_template==good['draft_template']
    assert FakeClient.calls==2
    print('PASS | 1차 거절 후 1회 보완 요청 성공')
    FakeClient.replies=[bad.copy(),bad.copy()];FakeClient.calls=0
    try:m.generate_draft('CK-03')
    except ValueError:pass
    else:raise AssertionError('2차 실패 미차단')
    assert FakeClient.calls==2
    print('PASS | 2차도 부적합하면 차단 및 종료')
print('결과: 5/5 통과 | 실제 Gemini/DB 호출 없음')
