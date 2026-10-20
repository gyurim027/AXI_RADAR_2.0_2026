"""승인 문장 전용 조회 회귀 테스트. 임시 JSON만 변경함."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.ai10_review_api import create_router
from app.services.ai10_operator_review import SOURCE, bootstrap


def main():
    passed = 0
    with tempfile.TemporaryDirectory(prefix="ai10_approved_test_") as tmp:
        store = Path(tmp) / "reviews.json"
        assert bootstrap(SOURCE, store) == 14
        app = FastAPI()
        app.include_router(create_router(store))
        client = TestClient(app)
        base = "/api/ai10/reviews"

        def check(title, condition):
            nonlocal passed
            assert condition, title
            passed += 1
            print(f"통과 | {title}")

        r = client.get(f"{base}/approved/CK-03")
        check("미승인 문장은 조회 차단", r.status_code == 404)
        r = client.get(f"{base}/approved/CK-99")
        check("존재하지 않는 CK는 404", r.status_code == 404)
        with patch.dict(os.environ, {"AI10_DEV_API_ENABLED": "1"}):
            r = client.post(f"{base}/CK-03/approve", json={
                "reviewer": "AI10_TEST", "note": "기능 시험", "acknowledge_findings": True, "evidence_source": "시험용 모의 근거(실제 원문 대조 아님)", "evidence_checked": True
            })
            check("검토자 승인 성공", r.status_code == 200 and r.json()["approved"] is True)
            r = client.get(f"{base}/approved/CK-03")
            data = r.json()
            check("승인 문장 정상 반환", r.status_code == 200 and data["rule_id"] == "CK-03" and bool(data["template"]))
            check("내부 검토 정보 노출 없음", set(data) == {"rule_id", "template", "revision", "approved_at"})
            r = client.post(f"{base}/CK-03/revoke", json={
                "reviewer": "AI10_TEST", "note": "기능 시험 승인 취소"
            })
            check("승인 취소 성공", r.status_code == 200 and r.json()["approved"] is False)
            check("승인 취소 후 즉시 조회 차단", client.get(f"{base}/approved/CK-03").status_code == 404)
            r = client.post(f"{base}/CK-04/reject", json={
                "reviewer": "AI10_TEST", "note": "기능 시험 반려"
            })
            check("반려 성공", r.status_code == 200 and r.json()["review_status"] == "rejected")
            check("반려 항목 조회 차단", client.get(f"{base}/approved/CK-04").status_code == 404)
            check("기존 CK 목록 유지", len(client.get(base).json()) == 14)
    print(f"결과: {passed}/{passed} 통과 | 실제 JSON/DB 변경 없음")


if __name__ == "__main__":
    main()
