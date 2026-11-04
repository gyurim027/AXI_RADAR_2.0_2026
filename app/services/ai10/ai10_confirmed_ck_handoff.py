"""상위 판정 기능에서 확인한 CK -> 기존 H-06 승인 문장 연결 (DB/API 호출 없음).

샘플 본문이나 AI-01 분류 결과로 CK를 새로 결정하지 않는다.
확정 판정값의 신뢰성/근거 자체는 상위 기능 및 운영자 검증 책임이다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.ai10_h06_ck_correspondence import validate_external_ck
from app.services.ai10_action_proposal import compose_action_proposal
from app.services.ai10_operator_review import STORE


def handoff_confirmed_ck(
    external_result: dict[str, Any] | None,
    *,
    confirmed_department: str | None = None,
    confirmed_legal_basis: str | None = None,
    store: Path = STORE,
) -> dict[str, Any]:
    """확정 CK 입력을 기존 승인 문장 연결부에 전달한다. 저장/생성/자동 판정 없음.

    상위 입력 계약(통합 전 임시 개발용):
    rule_id: CK-xx, judgment_confirmed: True, evidence_ref: 판정 근거 식별자.
    evidence_ref는 내부 참조 번호이며 원문·개인정보를 전달하지 않는다.
    """
    if not isinstance(external_result, dict):
        return {'status': '판정 입력 없음', 'rule_id': None, 'proposal': None}
    ck = external_result.get('rule_id')
    checked = validate_external_ck(ck)
    if checked['status'] != '식별자 확인':
        return {'status': 'CK 식별자 확인 불가', 'rule_id': None, 'proposal': None}
    rid = checked['rule_id']
    if external_result.get('judgment_confirmed') is not True:
        return {'status': '판정 미확정', 'rule_id': rid, 'proposal': None}
    evidence_ref = external_result.get('evidence_ref')
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        return {'status': '판정 근거 식별자 누락', 'rule_id': rid, 'proposal': None}
    proposal = compose_action_proposal(
        rid, confirmed_department=confirmed_department,
        confirmed_legal_basis=confirmed_legal_basis, store=store,
    )
    if proposal is None:
        return {'status': '승인된 문장 없음', 'rule_id': rid, 'proposal': None}
    return {'status': '승인 문장 연결됨', 'rule_id': rid, 'proposal': proposal}
