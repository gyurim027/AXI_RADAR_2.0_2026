"""AI-10 개발용 통합 입력 경로: CK 선택적 참고, 운영 DB/API 쓰기 없음."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
from app.services.ai10_case_draft import CaseInput, generate_case_draft, assess_case

ROOT = Path(__file__).resolve().parents[3]
CK_PATH = ROOT / 'data' / 'ai10_ck_rules_v0.4.1.json'


def find_optional_ck_reference(ck_reference: str | None) -> dict | None:
    """CK 조회 실패는 초안 생성 실패 사유가 아님. 참고데이터로만 돌려줌."""
    if not ck_reference or not CK_PATH.is_file():
        return None
    for item in json.loads(CK_PATH.read_text(encoding='utf-8-sig')).get('rules', []):
        if item.get('rule_id') == ck_reference:
            return {'rule_id': item.get('rule_id'), 'check_item': item.get('check_item'),
                    'check_required': item.get('check_required'), 'action_type': item.get('action_type'),
                    'data_limitation': item.get('data_limitation'),
                    'source_role': '조사 기반 참고 사례 / 판정·현장 사실 아님'}
    return None


def build_reference_context(case: CaseInput) -> str:
    ref=find_optional_ck_reference(case.ck_reference)
    if ref is None: return ''
    return ('\n[선택적 CK 참고 사례: 검증된 개별 현장 사실이 아니며 실제 근거와 상충하면 사용하지 않음]\n'
            + json.dumps(ref, ensure_ascii=False))


def generate_integrated_case_draft(case: CaseInput, *, generator: Callable[[str], dict | str] | None = None) -> dict:
    """기존 CK번호형 함수는 수정하지 않고 신규 사례 입력을 단일 경로로 수용."""
    context=build_reference_context(case)
    ref=find_optional_ck_reference(case.ck_reference)
    # 원본 generate_case_draft의 생성/검증/게이트를 그대로 활용.
    # 실제 호출과 주입 생성기가 같은 참고 문장을 사용한다.
    result = generate_case_draft(case, generator=generator, reference_context=context)
    result['ck_reference_status'] = ('참고 사례 연결' if ref else
                                   'CK 미제공' if not case.ck_reference else '참고 CK 조회 불가 / 생성 차단 아님')
    result['ck_reference_used_in_prompt'] = bool(context and result.get('model_call_allowed'))
    return result
