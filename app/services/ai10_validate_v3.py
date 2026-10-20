"""AI-10 오프라인 사전 검증 v3.

원본 배치/재시험/기준표를 읽기만 하고 새 보고서만 쓴다.
문장의 의미·법령 적법성에 대한 자동 승인 기능은 없다.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = ROOT / 'data' / 'ai10_ck_rules_v0.4.json'
DEFAULT_BATCH = ROOT / 'data' / 'ai10_draft_test_results.json'
DEFAULT_RETRY = ROOT / 'data' / 'ai10_ck03_retry.json'
DEFAULT_OUTPUT = ROOT / 'data' / 'ai10_review_report_v3.json'

# 검증 결과는 오류 확정이 아닌 독립적인 검토 신호이다.
EXTERNAL_ACTION = re.compile(r'(설치|보수|정비|단속|철거|보강|이첩)\s*(?:을|를)?\s*(?:요청|실시|진행|시행|수행|하[도록기]|해야)')
ACTION_TERMS = ('설치', '보수', '정비', '단속', '철거', '보강', '이첩')
UNCERTAIN = ('모른다', '알 수 없', '자료가 없', '기록이 없', '과거 기록', '실제와 다를', '추정', '오차', '조사가 없')
CLEAR_CONDITIONS = ('확인 결과에 따라', '확인 결과 필요', '필요한 것으로 확인', '필요하다고 확인', '필요성이 확인', '필요한 경우', '필요한지 검토', '필요 여부를 검토', '확인한 뒤 필요', '확인 후 필요')
ASSERTIONS = ('위반이 확인', '법령 위반', '불법으로 확인', '반드시 설치해야', '즉시 철거해야')

# v3: 기준표에 없는 강한 물리적 조치 표현은 승인하지 않고 별도 검토 대상으로 올린다.
# 행위 단어만으로 판단하지 않는다. 예: '설치 여부 확인'은 설치 지시가 아니다.
ACTION_CLAIMS = {
    '철거': re.compile(r'철거\s*(?:를|을|하도록|해|하[여는고]|요청|진행|실시|검토)'),
    '교체': re.compile(r'교체\s*(?:를|을|하도록|해|하[여는고]|요청|진행|실시|검토)'),
    '폐쇄': re.compile(r'폐쇄\s*(?:를|을|하도록|해|하[여는고]|요청|진행|실시|검토)'),
    '과태료 부과': re.compile(r'과태료\s*(?:를|을)?\s*부과'),
}
# 사실 여부 미확인인데 시설의 현존·부재 또는 손상 상태를 단정하는 대표 표현.
# 이 정규식의 탐지 범위는 제한적이며 의미 검증을 대신하지 못한다.
STATE_ASSERTION = re.compile(
    r'(?:시설|점자블록|표지판|볼라드|신호등|교통섬|분리대|카메라|보안등|울타리)'
    r'.{0,35}(?:실제로\s*)?(?:모두\s*)?'
    r'(?:설치되어\s*있지\s*않습니다|설치되어\s*있습니다|없습니다|파손되어\s*있습니다|고장났습니다|훼손되었습니다|존재하지\s*않습니다)'
)



def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def check(rule, draft):
    findings = []
    def flag(code, detail, category):
        findings.append({'code': code, 'category': category, 'detail': detail})

    if not isinstance(draft.get('rule_id'), str) or draft.get('rule_id') != rule['rule_id']:
        flag('ID_MISMATCH', 'CK 식별자가 기준표와 일치하지 않음', 'format')
    for k in ('rule_id', 'draft_template', 'review_note'):
        if not isinstance(draft.get(k), str) or not draft[k].strip():
            flag('MISSING_FIELD', f'{k} 누락 또는 공백', 'format')
    sentence = draft.get('draft_template') if isinstance(draft.get('draft_template'), str) else ''
    if len(sentence) > 600:
        flag('LONG_DRAFT', '문장 600자 초과', 'format')
    if re.search(r'\{[^{}]+\}', sentence):
        flag('VARIABLE_REVIEW', '문장 변수의 허용 목록 및 데이터 출처 검토 필요', 'integration')

    evid = rule.get('evidence_status')
    if evid in ('확인 필요', '근거 없음'):
        flag('EVIDENCE_STATUS', f'기준표 근거 상태: {evid}; 법적 확정 표현 금지', 'source')
    if '판정 테이블에 없음' in str(rule.get('judgment_type') or ''):
        flag('NO_JUDGMENT_MAPPING', '판정 테이블 미연결: 자동 후보 표시 불가', 'integration')
    if rule['rule_id'] in ('CK-02', 'CK-08'):
        flag('MAPPING_REVIEW', '실제 판정 결과와 연결 방식 확인 필요', 'integration')
    if any(x in sentence for x in ASSERTIONS):
        flag('ASSERTION_REVIEW', '위반 또는 의무를 확정하는 표현 가능성', 'content')

    # 출처에서 지원하지 않는 강한 조치 요청 후보를 분리한다.
    # 기준표 action_type의 명시적 지원 여부만 판정한다. 법적 허용 여부는 판정하지 않는다.
    allowed_action = str(rule.get('action_type') or '')
    for name, pattern in ACTION_CLAIMS.items():
        if pattern.search(sentence) and name not in allowed_action:
            flag('UNSUPPORTED_ACTION_REVIEW', f'조치 \"{name}\"는 기준표 조치유형에 없음: 운영자 확인 필요', 'content')

    # 근거 미관측인데도 존재·부재·파손을 사실로 단정하는 문장을 표시한다.
    # 인용문이나 확인 대상 설명은 오탐 가능성이 있어 검토 신호에 머무른다.
    if STATE_ASSERTION.search(sentence) and any(t in str(rule.get('data_limitation') or '') for t in UNCERTAIN):
        flag('UNVERIFIED_STATE_ASSERTION_REVIEW', '미확인 시설 상태의 확정 표현 가능성: 원천 근거 확인 필요', 'content')

    # 실제 설치 여부가 미관측인 상황에서 '설치 여부 확인'은 신규 설치 조치로 취급하지 않는다.
    # 조치 요청 제안은 원래 기준표에 있어도 현장 확인/필요성 조건을 사람이 반드시 점검한다.
    if any(word in (rule.get('action_type') or '') for word in ACTION_TERMS):
        if any(term in str(rule.get('data_limitation') or '') for term in UNCERTAIN):
            if re.search(r'(설치|보수|정비|단속|보강|철거).{0,18}(요청|진행|실시|검토)', sentence):
                if not any(cond in sentence for cond in CLEAR_CONDITIONS):
                    flag('ACTION_PREREQUISITE_REVIEW', '원천의 미관측 상태와 조치 필요성 확인 조건이 문장에 반영됐는지 확인', 'content')
    if rule['rule_id'] in ('CK-03','CK-06','CK-12','CK-13'):
        if not any(cond in sentence for cond in CLEAR_CONDITIONS):
            flag('SPECIFIC_CONDITION_REVIEW', '이 CK 유형은 실제 설치·상태 확인 이후의 필요성 검토가 중요한 사례', 'content')

    # 문장에 입력된 근거가 아닌 별도 법령번호/확정 수치 등장 여부만 검토 신호로 표기.
    context = ' '.join(str(v or '') for v in rule.values())
    for matched in set(re.findall(r'제\s*\d+\s*조(?:의\d+)?', sentence)):
        if matched.replace(' ', '') not in context.replace(' ', ''):
            flag('UNSOURCED_ARTICLE_REVIEW', f'근거에 없는 조문 표기: {matched}', 'content')
    for matched in set(re.findall(r'\d+(?:[.,]\d+)?\s*(?:m|km|초|%|건|곳)', sentence)):
        if matched.replace(' ', '') not in context.replace(' ', ''):
            flag('UNSOURCED_NUMBER_REVIEW', f'입력에 없는 수치·단위: {matched}', 'content')

    # 의미적 지원 여부는 자동 추정하지 않음. 모든 문장은 사람에게 남긴다.
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    parser.add_argument('--batch', type=Path, default=DEFAULT_BATCH)
    parser.add_argument('--retry', type=Path, default=DEFAULT_RETRY)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    a = parser.parse_args()
    rules = read_json(a.rules)['rules']
    batch = read_json(a.batch)
    original = {r['rule_id']: r for r in batch['results']}
    retry = read_json(a.retry) if a.retry.exists() else None
    if retry and retry.get('rule_id') != 'CK-03':
        raise ValueError('재시험 파일은 CK-03 전용입니다.')
    rows = []
    for rule in rules:
        rid = rule['rule_id']
        record = retry if (rid == 'CK-03' and retry) else original.get(rid)
        source = 'separate_retry' if rid == 'CK-03' and retry else 'original_batch'
        if record is None or record.get('status') == 'error':
            rows.append({'rule_id':rid,'source':source,'technical_status':'error',
                         'findings':[{'code':'NO_DRAFT','category':'format','detail':'초안 없음'}],
                         'manual_review_required':True,'approved':False})
            continue
        rows.append({'rule_id':rid,'source':source,'technical_status':'generated',
                     'draft_template':record.get('draft_template'), 'review_note':record.get('review_note'),
                     'evidence_status':rule.get('evidence_status'),
                     'findings':check(rule,record), 'manual_review_required':True,'approved':False})
    out = {'purpose':'오프라인 사전검토 v3; 승인이 아니며 원본 데이터 불변',
           'generated_at_utc':datetime.now(timezone.utc).isoformat(),
           'original_batch_success':batch['success'],'original_batch_errors':batch['errors'],
           'retry_used':bool(retry),'generated_count_for_review':sum(r['technical_status']=='generated' for r in rows),
           'approved_count':0,'results':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print('원본 성공/실패:',batch['success'],'/',batch['errors'])
    print('재시험:', '별도 기록 반영' if retry else '없음')
    print('검토 가능:',out['generated_count_for_review'],'/',len(rules),'| 승인:',out['approved_count'])
    for row in rows:
        codes=[f['code'] for f in row['findings']]
        print(f"{row['rule_id']}: {len(codes)}건 - {', '.join(codes) if codes else '자동 표시 없음(사람 검토 필수)'}")
    print('신규 보고서:',a.output)

if __name__ == '__main__':
    main()
