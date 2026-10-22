"""RADAR AI-10 최신 문장 틀 생성 보완안 (DB 쓰기/승인 없음).

배치 위치: app/services/ai10_draft.py (기존 파일 백업 후 교체)
기준: 통합 관리 대장 v0.4.1 05_03, 기능정의서 v0.5.2 H-06/H-07.
검증되지 않은 정보공개 회신·조문을 사실인 양 쓰지 않습니다.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json'

class DraftOutput(BaseModel):
    rule_id: str = Field(description='CK 항목 ID')
    draft_template: str = Field(description='자료 설명 + 확인 또는 요청의 두 문장')
    review_note: str = Field(description='운영자가 원문으로 확인해야 할 내용')

def load_rule(rule_id: str) -> dict:
    payload = json.loads(RULES_PATH.read_text(encoding='utf-8-sig'))
    for r in payload['rules']:
        if r['rule_id'] == rule_id:
            return r
    raise ValueError(f'최신 기준표에 없는 항목: {rule_id}')

def make_prompt(rule: dict, *, confirmed_source_text: str | None = None) -> str:
    """원문을 사람이 확인해서 전달하지 않았다면 특정 회신을 확인했다고 말하지 않음."""
    allowed = {key:rule.get(key) for key in (
        'rule_id','judgment_type','check_item','data_limitation',
        'check_required','action_type','evidence_status','notes'
    )}
    confirmed_source = confirmed_source_text.strip() if confirmed_source_text else None
    # CK-10: 최신 81번 예시의 '2.0m 미만'은 실제 측정 결과가 아님.
    ck10_safety = (
        'CK-10은 실제 측정 결과가 없는 유형별 초안입니다. '
        '81번의 기존 예시 문장이나 2.0m 미만이라는 판정값을 실제 관측 사실처럼 쓰지 마세요. '
        '도면 측정 폭과 현장 유효폭을 구별하고 실제 실측 필요성을 안내하세요.\n'
        if rule.get('rule_id') == 'CK-10' and not confirmed_source else ''
    )
    ck14_safety = (
        'CK-14의 data_limitation에 있는 신고 관련 서술은 유형별 가정·제약 설명이며 개별 대상의 확인된 신고 자료가 아닙니다. '
        '확정 근거 원문이 제공되지 않았으므로 신고 내역이 있다, 존재한다, 확보됐다, 확인됐다는 사실을 단정하지 마세요. '
        '신고 이력 자체의 확인 여부와 현재 반복 여부를 모두 미확정으로 표현하고 원문 확인을 요청하세요.\n'
        if rule.get('rule_id') == 'CK-14' and not confirmed_source else ''
    )
    return (
        ck10_safety + ck14_safety +
        'RADAR 2.0 AI-10의 유형별 조치 제안 문장 틀 초안을 작성하세요.\n'
        '정확히 두 문장으로 만드세요. 첫째는 데이터로 확인한 사실 또는 자료의 한계, '
        '둘째는 담당자가 확인하거나 요청할 조치입니다.\n'
        '자료가 없다는 상황과 과거 기록만 있다는 상황을 단정적으로 합치지 마세요. '
        '입력 data_limitation에 "없거나 과거 기록"처럼 미확정 선택지가 있으면 둘 중 어느 것도 확정하지 말고, '
        '"현재 확보한 자료만으로는 해당 시설의 현재 상태를 확인할 수 없습니다."처럼 공통으로 참인 한계만 쓰세요. '
        '개별 대상의 시설 상태·위반·반복·숫자를 지어내지 마세요.\n'
        '현장 확인 전에 설치나 단속을 요청하라고 명령하지 마세요. '
        '확인 결과에 따라 필요성을 검토하도록 표현하세요.\n'
        '확인되지 않은 정보공개 회신, 연월, 법령 조항을 문장에 포함하지 마세요. '
        '근거 상태 "확인됨"은 원문 회신 검증이 완료됐다는 뜻이 아닙니다.\n'
        '받는 부서와 법령 조문 후보는 문장 안에 임의로 넣지 마세요. '
        '확인할 것과 조치 종류는 입력에 있는 범위만 사용하세요.\n'
        '현재 입력은 유형별 기준이지 실제 후보별 현장 측정 결과가 아닙니다. '
        '유형별 초안을 내고 사용 승인이나 DB 저장을 수행하지 마세요.\n'
        '검증 원문이 전달되지 않았다면 "성남시정보공개 회신" 등 구체 출처를 주장하지 마세요.\n'
        '확정 근거 원문이 없다면 신고 내역이 검증되었다거나 확인되었다고 주장하지 마세요. '
        'review_note에서 null 같은 내부 자료형을 그대로 쓰지 말고 원문 미제공으로 설명하세요. '
        '띄어쓰기를 확인하고 자연스러운 한국어 두 문장으로 작성하세요.\n'
        '출력은 rule_id, draft_template, review_note를 가진 JSON만 만드세요.\n'
        f'CK: {json.dumps(allowed, ensure_ascii=False)}\n'
        f'운영자가 직접 대조한 확정 근거 원문(없으면 null): {json.dumps(confirmed_source, ensure_ascii=False)}'
        + load_planning_reference(str(rule.get('rule_id', '')))
    )

def load_planning_reference(rule_id: str) -> str:
    """실제 과업지시서에서 추출·요약한 CK 연관 항목만 전달한다.

    과업지시서는 계획 수립 용역 지시이며 시설 현황/법적 의무의 실증 근거가 아니다.
    원본 HWP 대신 버전 관리 가능한 검토용 발췌 JSON을 참조한다.
    """
    path = ROOT / 'data' / 'ai10_reference' / 'seongnam_mobility_plan_excerpt_2026.json'
    if not path.is_file():
        raise FileNotFoundError(f'AI-10 추가 근거자료가 없습니다: {path}')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    related = data['ck_references'].get(rule_id, [])
    if not related:
        return ''
    return (
        '\n[추가 근거자료 / 정책·계획 방향 참고]\n'
        f"자료명: {data['title']} (발행: {data['date']})\n"
        + '\n'.join(f"- {x['section']}: {x['content']}" for x in related)
        + '\n이 자료는 2026년 수립 용역의 과업지시서입니다. 이미 조사·설치·개선이 완료됐다고 쓰지 말고, '
          '개별 시설의 실제 상태·위반 여부·법적 의무를 확정하거나 법령 조문 검증자료처럼 인용하지 마세요. '
          'CK 기준표가 우선이며, 연관 항목만 계획 방향의 보조 근거로 활용하세요.\n'
    )


def _ck10_unverified_width_claim(text: str) -> bool:
    """보도 폭 실측 근거 없는 확정적 수치/기준미달 주장만 차단한다."""
    import re
    # 숫자 소수점은 분리하지 않는다.
    sentences = re.split(r'(?<=[가-힣])\.(?=\s|$)|[!?\n]', text)
    for sentence in sentences:
        for clause in re.split(r'[,;]|하지만|그러나|다만', sentence):
            if not re.search(r'보도|보행로|유효폭|폭|너비|도면|측정|실측', clause):
                continue
            numeric = re.search(r'\d+(?:\.\d+)?\s*(?:m|미터|cm|센티미터)', clause, re.I)
            deficit = re.search(r'기준\s*(?:미달|이하)|(?:폭|너비)[^,;]{0,24}(?:부족|좁|미달)', clause)
            if not (numeric or deficit):
                continue
            if re.search(r'확인되지\s*않|확인할\s*수\s*없|미확인|불명|여부|인지|가능성|추정|일\s*수\s*있|측정\s*필요|실측\s*필요|자료가\s*없|근거가\s*없', clause):
                # 한 절에 '불확실'과 '측정 결과 확정'이 동시에 있으면 차단.
                if re.search(r'(?:실측 결과|측정 결과|실제 폭은|폭은)\s*\d', clause):
                    return True
                continue
            return True
    return False


def _unsupported_ck14_evidence_claim(text: str) -> bool:
    """근거 미제공 시 신고 이력의 존재/확보/확인을 확정하는 명시적인 절을 차단.

    확인 필요·미확인·부정·인용 자체는 사실 단정으로 취급하지 않는다.
    이 검사는 사람이 하는 원문 검토를 대신하지 않는다.
    """
    import re
    # 반대 접속어와 문장 경계에서 절을 나누되 '존재하나'와 '존재하지만'은 남긴다.
    for clause in re.split(r'[.!?\n]|[,;]|\s(?:그러나|반면|다만)\s', text):
        if not re.search(r'신고\s*(?:내역|이력|기록)', clause):
            continue
        match = re.search(r'신고\s*(?:내역|이력|기록)(.{0,45})', clause)
        if not match:
            continue
        tail = match.group(1)
        # '신고 내역은 있으나 반복 여부는 모른다'는 뒤의 불확실성과 무관하게 존재를 단정.
        # 다만 '있는지/있는지는 미확정'은 존재 여부 자체를 유보하므로 허용.
        if re.search(r'(?:은|는|이|가)\s*(?:있(?:습니다|다|으며|으나|지만|고|음|는(?!지))|있어|있었|있다고)', tail):
            return True
        # 직접 확인하지 않았다는 설명 또는 확인/존재 여부를 묻는 표현은 허용.
        if re.search(r'(?:존재|확인|확보)(?:하는지|되는지|했는지|됐는지|하는\s*여부|여부)|'
                     r'(?:존재|확인|확보)(?:하지\s*않|되지\s*않|하지\s*못|할\s*수\s*없|된\s*바\s*없)|'
                     r'(?:존재|확인|확보)(?:했다고|됐다고|한다고|된다고)\s*(?:볼\s*수\s*없|보기\s*어렵)|'
                     r'존재하지\s*않', tail):
            continue
        if re.search(r'(?:은|는|이|가)\s*'
                     r'(?:존재(?:합니다|한다|함|하나|하지만|하며|하고|해|했)|'
                     r'확인(?:됩니다|된다|됨|되나|되지만|됐|했)|'
                     r'확보(?:됩니다|된다|됨|되나|되지만|됐|했))', tail):
            return True
        # 실제 Gemini 응답에서 발견된 '신고 내역은 있으나' 등 존재 단정.
        # 단정 뒤 다른 절의 '확인할 수 없다'는 표현으로 앞선 주장을 허용하지 않는다.
        if re.search(r'(?:은|는|이|가)\s*(?:있(?:습니다|다|으며|으나|지만|고|음|는(?!지))|있어|있었|있다고)', tail):
            return True
    return False


def validate_draft(result: DraftOutput, rule_id: str, *, confirmed_source_text: str | None = None) -> DraftOutput:
    if result.rule_id != rule_id:
        raise ValueError('AI가 다른 CK 번호를 반환했습니다.')
    # 소수점은 CK-10 등에서 쓰일 수 있으므로 경계 검사만 수행
    import re
    n=len(re.findall(r'(?<=[가-힣])\.(?=\s|$)', result.draft_template))
    if n != 2:
        raise ValueError('최신 기획의 두 문장 구성에 맞지 않습니다. 운영자 재검토가 필요합니다.')
    if rule_id == 'CK-10' and not (confirmed_source_text and confirmed_source_text.strip()):
        if _ck10_unverified_width_claim(result.draft_template):
            raise ValueError('CK-10 검증된 측정 근거 없이 보도 폭이나 기준 미달을 단정했습니다.')
    if any(expr in result.draft_template for expr in ('없거나 과거', '없거나 오래된', '없는지 과거')):
        raise ValueError('자료 부재와 과거 기록을 하나의 사실로 묶었습니다. 원문 확인 전 상태를 단정할 수 없습니다.')
    import re
    if re.search(r'(설치|정비|보수|단속)(를|을)?\s*(요청|실시|시행)(하시기 바랍니다|해 주세요|해야 합니다|하십시오)', result.draft_template) and '검토' not in result.draft_template:
        raise ValueError('현장 확인 전 조치 실행을 단정했습니다. 확인 결과에 따른 필요성 검토로 작성하세요.')
    if not confirmed_source_text and ('정보공개 회신' in result.draft_template or '정보공개청구 회신' in result.draft_template):
        raise ValueError('검증한 원문 없이 정보공개 회신을 근거라고 주장했습니다.')
    if re.search(r'(?<![a-zA-Z])null(?![a-zA-Z])', result.review_note, re.I):
        raise ValueError('운영자 검토 문장에 내부 값 null이 노출됐습니다.')
    if rule_id == 'CK-14' and not (confirmed_source_text and confirmed_source_text.strip()):
        if _unsupported_ck14_evidence_claim(result.draft_template):
            raise ValueError('CK-14 근거 원문 없이 신고 이력을 확인했다고 단정했습니다.')
    return result

def generate_draft(rule_id: str, *, confirmed_source_text: str | None = None) -> DraftOutput:
    """최대 2회 Gemini 호출: 첫 응답이 검증에 실패한 때 한 번만 보완 요청.
    승인/DB 저장 없음. 연결 장애나 JSON 형식 오류는 자동 재시도하지 않음.
    """
    from dotenv import load_dotenv
    from google import genai
    load_dotenv(ROOT / '.env', override=True)
    api_key=os.getenv('GEMINI_API_KEY'); model=os.getenv('GEMINI_MODEL')
    if not api_key or not model:
        raise RuntimeError('.env GEMINI_API_KEY / GEMINI_MODEL을 확인하세요.')
    rule=load_rule(rule_id)
    prompt=make_prompt(rule,confirmed_source_text=confirmed_source_text)
    print(f'[AI-10] {rule_id} 최신 기준 Gemini 초안 생성 시작',flush=True)
    client=genai.Client(api_key=api_key)
    try:
        for attempt in (1,2):
            # 실제 AI-10 프롬프트로 정상 응답이 확인된 기본 호출을 사용합니다.
            # 구조화 응답 스키마 요청에서 반복된 503 문제를 회피합니다.
            response=client.models.generate_content(model=model, contents=prompt)
            response_text=(response.text or '').strip()
            # 기본 호출은 JSON을 ```json ... ``` 코드 블록으로 감쌀 수 있습니다.
            if response_text.startswith('```'):
                lines=response_text.splitlines()
                if len(lines) >= 3 and lines[-1].strip() == '```':
                    response_text='\n'.join(lines[1:-1]).strip()
            raw=DraftOutput.model_validate_json(response_text)
            try:
                result=validate_draft(raw,rule_id,confirmed_source_text=confirmed_source_text)
            except ValueError as exc:
                if attempt==2:
                    raise ValueError(f'2회 생성 모두 기준 미충족, 미승인·미저장: {exc}') from exc
                print(f'[AI-10] 1차 문장 검증 실패: {exc} / 보완 요청 1회',flush=True)
                prompt += ('\n이전 초안은 아래 검증 문제로 사용 불가입니다: '
                           + str(exc) + '\n이전 문장: ' + raw.draft_template
                           + '\n위 문제를 피하면서 두 문장 JSON으로 새로 작성하세요. '
                           '자료 상태가 미확정이면 현재 상태를 확인할 수 없다고 쓰세요. '
                           '현장 확인 전 설치를 직접 명령하지 말고 필요성을 검토하라고 쓰세요.')
                continue
            print(f'[AI-10] {rule_id} 초안 생성 완료 (검토 미완료)',flush=True)
            return result
        raise RuntimeError('예상하지 못한 생성 루프 종료')
    finally:
        client.close()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('ck',help='CK-01 등')
    parser.add_argument('--generate',action='store_true')
    args=parser.parse_args()
    if args.generate:
        try:
            print(generate_draft(args.ck).model_dump_json(indent=2))
        except ValueError as exc:
            parser.exit(2, f'[AI-10] 문장 검증 실패 (승인/저장 안 함): {exc}\n')
    else:
        print(make_prompt(load_rule(args.ck)))
