"""H-04 가상 구별 근거표와 연간 보고서 문장 틀. LLM/DB/네트워크 없음.

가상 계약을 명시적으로 검증한다. 회차 확정, 완전성, 권한은 실제 서비스에서
공식 DB와 로그인 사용자로부터 구성해야 하며 클라이언트의 표시는 신뢰하면 안 된다.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from .e02 import validate_card
from .e03 import refine_card
from .f06 import validate_request as validate_target_request

SCHEMA='ai07.h04.synthetic.v0.1'
DISTRICTS=('수정구','중원구','분당구')
DECISIONS=('candidate','confirmed_target','excluded','held')
HEADINGS=('현황','데이터 근거','관련 기준','데이터로 모르는 것','조치 제안')


def _keys(value,expected):
    if not isinstance(value,dict) or set(value)!=set(expected):raise ValueError('invalid_fields')


def validate_report(data):
    _keys(data,['schema_version','data_kind','run_id','report_year','run_status',
                'snapshot_complete','scope','candidates'])
    if data['schema_version']!=SCHEMA or data['data_kind']!='synthetic':
        raise ValueError('synthetic_contract_required')
    if data['run_status']!='confirmed':raise ValueError('run_not_confirmed')
    if data['snapshot_complete'] is not True:raise ValueError('incomplete_snapshot')
    if type(data['report_year']) is not int or not 1000<=data['report_year']<=9999:
        raise ValueError('invalid_report_year')
    if not isinstance(data['run_id'],str) or not data['run_id'].strip():raise ValueError('invalid_run_id')
    scope=data['scope'];_keys(scope,['role','district'])
    if scope['role']=='city' and scope['district'] is None:pass
    elif scope['role']=='district' and scope['district'] in DISTRICTS:pass
    else:raise ValueError('invalid_scope')
    if not isinstance(data['candidates'],list) or len(data['candidates'])>100000:
        raise ValueError('invalid_candidates')
    seen=set();versions=set()
    for row in data['candidates']:
        _keys(row,['district','request'])
        if row['district'] not in DISTRICTS:raise ValueError('invalid_district')
        r=row['request']
        _keys(r,['schema_version','data_kind','card','decision','department','action','laws'])
        if r['schema_version']!='ai07.f06.synthetic.v0.1' or r['data_kind']!='synthetic':
            raise ValueError('synthetic_contract_required')
        card=r['card'];validate_card(card)
        if card['run_id']!=data['run_id']:raise ValueError('mixed_run')
        if card['calculation_year']!=data['report_year']:raise ValueError('mixed_calculation_year')
        if card['gid'] in seen:raise ValueError('duplicate_candidate')
        seen.add(card['gid']);versions.add(card['formula_version'])
        decision=r['decision'];_keys(decision,['run_id','gid','status','record_id'])
        if (decision['run_id'],decision['gid'])!=(card['run_id'],card['gid']):
            raise ValueError('mixed_decision_identity')
        if not isinstance(decision['record_id'],str) or not decision['record_id'].strip():
            raise ValueError('missing_decision_record')
        if decision['status'] not in DECISIONS:raise ValueError('invalid_decision')
        # 보고서 조치/조문은 확정 대상의 검토된 입력만 사용한다.
        if decision['status']=='confirmed_target':validate_target_request(r)
    if len(versions)>1:raise ValueError('mixed_formula_versions')


def build_report(data):
    try:validate_report(data)
    except ValueError as exc:
        return {'schema_version':SCHEMA,'status':'blocked','report_text':None,
                'error_codes':[str(exc)],'llm_called':False,'external_api_called':False,'db_written':False}
    scope=data['scope']
    districts=DISTRICTS if scope['role']=='city' else (scope['district'],)
    rows=[r for r in data['candidates'] if r['district'] in districts]
    # 카드에서 다시 생성하며 기존 설명문이나 검증 표시는 신뢰하지 않는다.
    explanations=[(r,refine_card(r['request']['card'])) for r in rows]
    summary=[]
    for district in districts:
        selected=[r for r in rows if r['district']==district]
        states=Counter(r['request']['decision']['status'] for r in selected)
        scores=[Decimal(r['request']['card']['score']) for r in selected if r['request']['card']['score'] is not None]
        # 점수 분포는 통계 집계만 하며 새로운 위험 점수/순위를 계산하지 않는다.
        buckets=Counter('0~25 미만' if v<25 else '25~50 미만' if v<50 else '50~75 미만' if v<75 else '75 이상' for v in scores)
        labels=Counter(e['label'] for r in selected for e in r['request']['card']['evidence'])
        summary.append({'district':district,'candidate_count':len(selected),
                        'target_count':states['confirmed_target'],'held_count':states['held'],
                        'excluded_count':states['excluded'],'undecided_count':states['candidate'],
                        'known_score_count':len(scores),'missing_score_count':len(selected)-len(scores),
                        'score_min':str(min(scores)) if scores else None,'score_max':str(max(scores)) if scores else None,
                        'score_distribution':{key:buckets[key] for key in ('0~25 미만','25~50 미만','50~75 미만','75 이상')},
                        'evidence_labels':sorted(labels)})
    overview=['집계 범위: 입력받은 완전한 후보 스냅샷. 전체 격자 수와는 다릅니다.',
              '점수 구간은 이 가상 시험의 표시용 구간이며 위험 등급이 아닙니다.']
    for s in summary:
        overview.append(f"{s['district']}: 후보 {s['candidate_count']}개, 확정 대상 {s['target_count']}개, 보류 {s['held_count']}개, 제외 {s['excluded_count']}개, 미결정 {s['undecided_count']}개. 점수 미제공 {s['missing_score_count']}개.")
        overview.append('점수 분포: '+', '.join(f'{k}: {v}개' for k,v in s['score_distribution'].items()))
        overview.append('입력에 있는 근거 항목: '+(', '.join(s['evidence_labels']) or '미제공'))
    evidence=[];limitations=[];laws={};actions=[];source_refs=[]
    for r,ex in explanations:
        req=r['request'];card=req['card']
        evidence.append(f"[{r['district']} / {card['gid']} / 결정 상태 {req['decision']['status']}]\n{ex['explanation']}")
        source_refs.extend({'gid':card['gid'],**ref} for ref in ex['source_refs'])
        limitations.extend(f"{card['gid']}: {item}" for item in ex['limitations'])
        if card['score'] is None:limitations.append(f"{card['gid']}: 점수 미제공.")
        if card['rank'] is None:limitations.append(f"{card['gid']}: 순위 미제공.")
        if card['calculation_status']!='approved':limitations.append(f"{card['gid']}: 카드의 산정 결과 승인 상태는 {card['calculation_status']}입니다. 회차 확정 표시가 산식 승인을 뜻하지 않습니다.")
        if req['decision']['status']=='confirmed_target':
            for law in req['laws']:
                key=law['reference_id']
                if key in laws and laws[key]!=law:
                    return {'schema_version':SCHEMA,'status':'blocked','report_text':None,
                            'error_codes':['conflicting_law_reference'],'llm_called':False,'external_api_called':False,'db_written':False}
                laws[key]=deepcopy(law)
            if not req['laws']:limitations.append(f"{card['gid']}: 확인된 근거 조문 미제공.")
            actions.append(f"[{r['district']} / {card['gid']}] 받는 부서: {req['department']['name']} / 검토된 입력 제안: {req['action']['text']}")
    limitations+=['민원의 점수 반영 여부는 현재 가상 입력 계약에 없어 모름으로 표시합니다.',
                  '후보 수나 민원 0건을 안전함으로 해석하지 않습니다.',
                  '설명은 전달받은 값으로 작성했으며 원자료나 산식을 재검산하지 않았습니다.']
    sections=[{'title':HEADINGS[0],'text':'\n'.join(overview)},
              {'title':HEADINGS[1],'text':'\n\n'.join(evidence) or '제공된 후보 스냅샷에 후보가 없습니다.'},
              {'title':HEADINGS[2],'text':'\n'.join(f"{l['title']} {l['article']}: {l['text']}" for l in laws.values()) or '근거 조문 확인 중'},
              {'title':HEADINGS[3],'text':'\n'.join(dict.fromkeys(limitations))},
              {'title':HEADINGS[4],'text':'\n'.join(actions) or '확정 대상의 검토된 조치 제안이 없습니다.'}]
    title=f"[가상 자료 시험] {data['report_year']}년 {'3개 구' if scope['role']=='city' else scope['district']} 연간 검토 보고서 초안"
    text=title+'\n실행: '+data['run_id']+'\n사람이 검토·수정하기 전의 문장 틀 초안입니다.\n\n'
    text+='\n\n'.join(f"{i}. {s['title']}\n{s['text']}" for i,s in enumerate(sections,1))
    return {'schema_version':SCHEMA,'data_kind':'synthetic','status':'draft',
            'run_id':data['run_id'],'scope':deepcopy(scope),'district_summary':summary,
            'sections':sections,'report_text':text,'source_refs':source_refs,
            'generation_method':'local_template','error_codes':[],
            'llm_called':False,'external_api_called':False,'db_written':False}
