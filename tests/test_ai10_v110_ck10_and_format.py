"""최신 CK-10 자료 미확정 경계 + 기존 상세 출력 형식 확인 (실제 Gemini/DB 호출 없음)."""
import sys
import os
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.ai10_draft import DraftOutput, load_rule, make_prompt, validate_draft

def check(name,ok):
    if not ok: raise AssertionError(name)
    print('PASS | '+name)

r=load_rule('CK-10')
prompt=make_prompt(r)
check('CK-10 실측 전 2.0m 미만 단정 금지 지침', '실제 관측 사실처럼 쓰지 마세요' in prompt)
unsafe=DraftOutput(rule_id='CK-10',draft_template='도면에서 잰 보도 폭이 2.0m보다 좁습니다. 현장에서 폭을 확인해 주세요.',review_note='확인 필요')
try:
    validate_draft(unsafe,'CK-10')
    raise AssertionError('실측 없는 폭 단정이 허용됨')
except ValueError as e:
    check('CK-10 실측 없는 폭 단정 차단','실제 측정값 없이' in str(e))
safe=DraftOutput(rule_id='CK-10',draft_template='현재 자료만으로 실제 보행 유효폭을 알 수 없습니다. 현장에서 유효폭을 실측해 주시기 바랍니다.',review_note='실측 필요')
validate_draft(safe,'CK-10')
check('CK-10 안전한 조건부 문장 허용',True)
with tempfile.TemporaryDirectory() as d:
    # Windows의 콘솔 코드 페이지와 무관하게 자식 Python 출력을 UTF-8로 고정합니다.
    env=os.environ.copy()
    env['PYTHONIOENCODING']='utf-8'
    env['PYTHONUTF8']='1'
    ret=subprocess.run(
        [sys.executable,str(ROOT/'tests/test_ai10_complaint_latest_compare_v052.py'),
         '--all','--output',str(Path(d)/'out.json')],
        capture_output=True,encoding='utf-8',errors='replace',env=env,
    )
    stdout=ret.stdout or ''
    if ret.returncode != 0 or '완료: 총 22건' not in stdout:
        print(f'[하위 시험 종료 코드] {ret.returncode}',flush=True)
        print('[하위 시험 표준 오류]\n'+(ret.stderr or '(없음)'),flush=True)
        print('[하위 시험 마지막 출력]\n'+stdout[-1600:],flush=True)
    check('22건 상세 출력 실행',ret.returncode==0 and '완료: 총 22건' in stdout)
    for key in ('[신고인의 주장]','[사실 확인]','[미확인]','[CK 판정 기준]','[CK 자료 한계]','[CK 확인 사항]','[CK 조치 종류]','[법령 근거 후보/검증 전]','[최종 후보 조치 제안]'):
        check('상세 출력 '+key,key in stdout)
print('결과: 전체 통과 | 실제 Gemini/DB 호출 없음')
