"""H-06 판정 결과 종류 ↔ 05_03 CK 대응표 읽기 전용 대조.

근거: 기획·관리 대장 v0.4.1 05_03 및 기능정의서 v0.5.2 H-06.
입력은 다른 RADAR 기능이 제공한 *판정 결과 종류*이며 민원 원문이 아님.
정확히 일치하는 규칙만 후보로 돌려주고 판정·승인·저장은 수행하지 않는다.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json'


def compare_judgment_to_ck(judgment_type: str | None, *, rules_path: Path = RULES_PATH) -> dict[str, Any]:
    """문서의 판정 결과 종류와 정확히 일치할 때만 CK를 제시한다.

    ``-``로 시작하는 항목은 실제 판정 테이블 값이 아닌 주석/도면·과거 자료이므로
    이 함수에서 자동 연결하지 않는다. 같은 판정이 여러 CK인 경우 선택하지 않는다.
    """
    if not isinstance(judgment_type, str) or not judgment_type.strip():
        return {'status': '입력 부족', 'ck_candidates': [], 'detail': '판정 결과 종류가 전달되지 않았습니다.'}
    supplied = judgment_type.strip()
    data = json.loads(Path(rules_path).read_text(encoding='utf-8-sig'))
    candidates = []
    for rule in data['rules']:
        ref = rule.get('judgment_type')
        if not isinstance(ref, str) or not ref.strip() or ref.lstrip().startswith('-'):
            continue
        if supplied == ref.strip():
            candidates.append({'rule_id': rule['rule_id'], 'check_item': rule.get('check_item'), 'action_type': rule.get('action_type')})
    if not candidates:
        return {'status': '대응 없음', 'ck_candidates': [], 'detail': '05_03과 정확히 일치하는 판정 결과 종류가 없습니다. 자동 추정하지 않습니다.'}
    if len(candidates) > 1:
        return {'status': '추가 확인 필요', 'ck_candidates': candidates, 'detail': '하나의 판정 결과가 여러 CK에 연결됩니다. 확인 항목을 검토해야 합니다.'}
    return {'status': '대응 후보 1건', 'ck_candidates': candidates, 'detail': '문자열 대응 결과이며 대상별 판정·조치 확정이나 문장 승인 결과가 아닙니다.'}


def validate_external_ck(rule_id: str | None, *, rules_path: Path = RULES_PATH) -> dict[str, Any]:
    """다른 RADAR 기능이 확정해 전달한 CK 식별자만 형식·존재 여부 확인.

    이 함수는 민원 원문이나 판정 수치를 분석하여 CK를 새로 결정하지 않는다.
    대응표에 식별자가 존재한다는 것은 시설 조건이 참임을 증명하지 않는다.
    """
    if not isinstance(rule_id, str) or not rule_id.strip():
        return {'status': '입력 부족', 'rule_id': None, 'detail': '상위 기능에서 CK 식별자를 전달하지 않았습니다. 대조 미실행과 CK 불일치를 구분해야 합니다.'}
    supplied = rule_id.strip()
    data = json.loads(Path(rules_path).read_text(encoding='utf-8-sig'))
    ids = {entry['rule_id'] for entry in data['rules']}
    if supplied not in ids:
        return {'status': '기준표에 없음', 'rule_id': None, 'detail': '05_03에 없는 CK 번호입니다. 추정 연결하지 않습니다.'}
    return {'status': '식별자 확인', 'rule_id': supplied, 'detail': '05_03의 기존 CK 식별자 존재만 확인했습니다. 조건 충족·판정 근거·승인을 검증한 것은 아닙니다.'}


# 민원 적재 규칙 명세서 v1.1(5~6장, 11장)에서는 79번 AI-01 결과가
# CK 판정값이 아니고 초기 적재 시 NULL이다. 이 읽기 전용 점검 함수는
# 79번 데이터만으로 CK를 확정하거나 81/82번을 생성하지 않는다.
AI01_OUTPUT_FIELDS = ('가린_요약', '관련_여부', '보행_유형', '분류_신뢰도', '판단근거')


def inspect_complaint_handoff(complaint_row: dict[str, Any] | None) -> dict[str, Any]:
    """79번 민원 행의 AI-01 준비 상태를 검토한다. 민원 원문/개인정보는 반환하지 않는다.

    79번의 관련_여부/보행_유형/반복_제목/중복_표시는 CK 판정값이 아니므로
    CK 후보를 산출하지 않는다. 실제 CK 연계는 다른 판정 기능의 명시적
    판정 결과와 공식 05_03 대응 조건을 확인한 뒤에만 가능하다.
    """
    if not isinstance(complaint_row, dict):
        return {'status': '입력 부족', 'ck_candidates': [],
                'detail': '79번 민원 행이 제공되지 않았습니다.'}
    missing = [name for name in AI01_OUTPUT_FIELDS if complaint_row.get(name) is None or
               (isinstance(complaint_row.get(name), str) and not complaint_row[name].strip())]
    if missing:
        return {'status': 'AI-01 결과 미완료 또는 누락', 'ck_candidates': [],
                'missing_fields': missing,
                'detail': '79번 AI-01 결과 미입력과 CK 기준 불일치는 다릅니다. CK를 자동 생성하지 않습니다.'}
    return {'status': 'AI-01 결과 입력됨 · CK 판정 별도 필요', 'ck_candidates': [],
            'missing_fields': [],
            'detail': 'AI-01 관련 여부·보행 유형은 CK 판정이 아닙니다. 판정 기능 결과가 별도로 필요합니다.'}
