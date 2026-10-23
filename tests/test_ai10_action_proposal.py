"""실제 저장소 변경 없는 AI-10 조치 제안 결과 구성 독립 시험.
설치: tests/test_ai10_action_proposal.py
실행: uv run python tests/test_ai10_action_proposal.py
"""
import json
import tempfile
from pathlib import Path

from app.services.ai10_action_proposal import compose_action_proposal


def main():
    with tempfile.TemporaryDirectory() as folder:
        store = Path(folder) / "review.json"
        def item(rid, status, approved, sentence):
            return {"rule_id": rid, "review_status": status, "approved": approved,
                    "edited_template": sentence, "revision": 2, "approved_at": "TEST_TIME"}
        data = {"items": {
            "CK-01": item("CK-01", "approved", True, "보도 상태 확인 후 정비 필요성을 검토합니다."),
            "CK-02": item("CK-02", "pending", False, "미승인 문장"),
            "CK-03": item("CK-03", "rejected", False, "반려 문장"),
            "CK-04": item("CK-04", "pending", False, "승인 취소 문장"),
            "CK-05": item("CK-05", "approved", True, "  "),
            "CK-06": item("CK-06", "approved", False, "상태 불일치 문장"),
        }}
        store.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        before = store.read_bytes()
        checks = []
        def check(name, expression):
            assert expression, name
            checks.append(name)
            print("통과 | " + name)

        result = compose_action_proposal("CK-01", confirmed_department="확인된 시험 부서",
                                         confirmed_legal_basis="확인된 시험 조문", store=store)
        check("승인 문장 반환", result["action_proposal_sentence"] == data["items"]["CK-01"]["edited_template"])
        check("전달받은 부서·조문 유지", result["receiving_department"] == "확인된 시험 부서" and result["confirmed_legal_basis"] == "확인된 시험 조문")
        check("정보 갖춘 경우 표시 준비", result["ready_for_full_display"] is True and not result["missing_information"])
        check("미승인 문장 차단", compose_action_proposal("CK-02", store=store) is None)
        check("반려 문장 차단", compose_action_proposal("CK-03", store=store) is None)
        check("승인 취소 문장 차단", compose_action_proposal("CK-04", store=store) is None)
        check("빈 승인 문장 차단", compose_action_proposal("CK-05", store=store) is None)
        check("승인 상태 불일치 차단", compose_action_proposal("CK-06", store=store) is None)
        partial = compose_action_proposal("CK-01", store=store)
        check("누락값 임의 생성 방지", partial["receiving_department"] is None and partial["confirmed_legal_basis"] is None)
        check("누락 정보 별도 표시", partial["missing_information"] == ["받는 부서", "확인된 근거 조문"] and partial["ready_for_full_display"] is False)
        check("원본 시험 저장소 변경 없음", store.read_bytes() == before)
        try:
            compose_action_proposal("CK-99", store=store)
        except ValueError as error:
            check("없는 CK 명확하게 오류 처리", "존재하지 않는 CK 번호" in str(error))
        else:
            raise AssertionError("없는 CK가 오류 없이 처리됨")
        print(f"결과: {len(checks)}/{len(checks)} 통과 | 실제 JSON/DB 변경 없음")

if __name__ == "__main__":
    main()
