"""AI-10 H-06 독립 연결부: 승인된 CK 문장과 외부에서 확인한 정보만 구성.

후보 선정, CK 자동 매핑, 부서/법령 추론, Gemini/DB 호출은 수행하지 않습니다.
설치: app/services/ai10_action_proposal.py
"""
from pathlib import Path
from typing import Optional

from app.services.ai10_operator_review import STORE, get_item, load_store


def compose_action_proposal(
    rule_id: str,
    *,
    confirmed_department: Optional[str] = None,
    confirmed_legal_basis: Optional[str] = None,
    store: Path = STORE,
) -> Optional[dict]:
    """승인된 문장만 반환합니다. 미승인/반려/취소는 None을 반환합니다.

    rule_id는 외부에서 이미 확인한 CK 번호입니다. 추론하지 않습니다.
    confirmed_*는 호출 측에서 확인한 경우에만 전달해야 합니다.
    """
    data = load_store(store)
    item = get_item(data, rule_id)
    if item.get("review_status") != "approved" or item.get("approved") is not True:
        return None

    sentence = item.get("edited_template")
    if not isinstance(sentence, str) or not sentence.strip():
        return None

    department = confirmed_department.strip() if isinstance(confirmed_department, str) else None
    legal_basis = confirmed_legal_basis.strip() if isinstance(confirmed_legal_basis, str) else None
    department = department or None
    legal_basis = legal_basis or None

    missing = []
    if department is None:
        missing.append("받는 부서")
    if legal_basis is None:
        missing.append("확인된 근거 조문")

    return {
        "rule_id": rule_id,
        "action_proposal_sentence": sentence.strip(),
        "receiving_department": department,
        "confirmed_legal_basis": legal_basis,
        "missing_information": missing,
        "ready_for_full_display": not missing,
        "revision": item.get("revision"),
        "approved_at": item.get("approved_at"),
    }
