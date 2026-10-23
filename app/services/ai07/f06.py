"""F-06 요청안 문장 틀 시험. 가상 계약, I/O/자동발송/DB쓰기/LLM호출 없음.

담당 부서 판정, 대상 확정, 조치 제안 작성, 법령 검색은 하지 않는다.
호출자가 전달한 검토 상태는 시험용 입력일 뿐 실제 승인 인증이 아니다.
실제 서버는 권한 확인 후 공식 기록에서 이 값을 구성해야 한다.
"""
from copy import deepcopy
from .e02 import validate_card, CardError
from .e03 import refine_card

SCHEMA='ai07.f06.synthetic.v0.1'


def _keys(value, keys):
    if not isinstance(value,dict) or set(value)!=set(keys):
        raise ValueError('invalid_fields')


def _text(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2000 or any(ord(c)<32 for c in value):
        raise ValueError('invalid_text')


def validate_request(data):
    _keys(data,['schema_version','data_kind','card','decision','department','action','laws'])
    if data['schema_version']!=SCHEMA or data['data_kind']!='synthetic':
        raise ValueError('synthetic_contract_required')
    validate_card(data['card'])
    card=data['card'];decision=data['decision']
    _keys(decision,['run_id','gid','status','record_id'])
    if (decision['run_id'],decision['gid'])!=(card['run_id'],card['gid']):
        raise ValueError('mixed_run_or_grid')
    _text(decision['record_id'])
    if decision['status']!='confirmed_target':
        raise ValueError('target_not_confirmed')
    department=data['department'];_keys(department,['name','status'])
    if department['status']!='confirmed' or department['name'] in (None,'','확인 필요','담당 미정'):
        raise ValueError('department_not_confirmed')
    _text(department['name'])
    action=data['action'];_keys(action,['text','review_status','reference_id'])
    if action['review_status']!='reviewed':
        raise ValueError('action_not_reviewed')
    _text(action['text']);_text(action['reference_id'])
    if not isinstance(data['laws'],list) or len(data['laws'])>20:
        raise ValueError('invalid_laws')
    ids=set()
    for law in data['laws']:
        _keys(law,['reference_id','title','article','text','review_status'])
        if law['review_status']!='confirmed':
            raise ValueError('law_not_confirmed')
        for key in ['reference_id','title','article','text']:_text(law[key])
        if law['reference_id'] in ids:raise ValueError('duplicate_law_reference')
        ids.add(law['reference_id'])


def build_request(data):
    """근거 문장을 카드에서 다시 생성해 조작된 '검증 통과' 설명문 사용을 방지한다."""
    try:
        validate_request(data)
    except (ValueError,CardError) as exc:
        return {'schema_version':SCHEMA,'status':'blocked','error_codes':[str(exc)],
                'request_text':None,'automatic_send':False,'llm_called':False,
                'external_api_called':False,'db_written':False}
    card=data['card'];explanation=refine_card(card)
    if explanation['status']!='ok':
        return {'schema_version':SCHEMA,'status':'blocked','error_codes':['invalid_evidence'],
                'request_text':None,'automatic_send':False,'llm_called':False,
                'external_api_called':False,'db_written':False}
    law_lines=[f"{law['title']} {law['article']}: {law['text']}" for law in data['laws']]
    law_text='\n'.join(law_lines) if law_lines else '근거 조문 확인 중'
    limitations=list(explanation['limitations'])
    if not law_lines:limitations.append('확인된 근거 조문이 제공되지 않았습니다.')
    limitations.append('민원의 점수 반영 여부는 이 입력 계약에 없어 확인할 수 없습니다.')
    text='\n\n'.join([
        '[가상 자료 시험 / 관할 요청안 초안 / 발송되지 않음]',
        f"받는 부서: {data['department']['name']}",
        f"대상: {card['place']} / 격자 {card['gid']} / 실행 {card['run_id']}",
        f"결정 기록: {data['decision']['record_id']} (입력에 확정 대상으로 표시)",
        '1. 데이터 근거\n'+explanation['explanation'],
        '2. 관련 기준\n'+law_text,
        '3. 전달받은 조치 제안\n'+data['action']['text'],
        '4. 데이터로 모르는 것\n'+'\n'.join(limitations),
        '사용 전 담당자가 대상·받는 부서·근거·요청 내용을 확인해 주세요.'
    ])
    return {'schema_version':SCHEMA,'data_kind':'synthetic','status':'draft',
            'run_id':card['run_id'],'gid':card['gid'],'request_text':text,
            'generation_method':'local_template','explanation':explanation,
            'source_refs':deepcopy(explanation['source_refs']),
            'law_refs':[law['reference_id'] for law in data['laws']],
            'action_reference_id':data['action']['reference_id'],
            'facts':deepcopy(data),'limitations':limitations,'error_codes':[],
            'automatic_send':False,'llm_called':False,'external_api_called':False,'db_written':False}
