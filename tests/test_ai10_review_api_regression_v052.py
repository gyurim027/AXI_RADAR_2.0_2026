"""개발용 API 오프라인 회귀 시험. 실제 프로젝트 JSON/DB 수정 없음."""
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
from app.services.ai10_operator_review import bootstrap, SOURCE


def main():
    passed = 0
    with tempfile.TemporaryDirectory(prefix="ai10_api_test_") as temp_dir:
        store = Path(temp_dir) / "reviews.json"
        assert bootstrap(SOURCE, store) == 14
        app = FastAPI()
        app.include_router(create_router(store))
        client = TestClient(app)
        prefix = "/api/ai10/reviews"

        def check(name, condition):
            nonlocal passed
            if not condition:
                raise AssertionError(name)
            passed += 1
            print(f"통과 | {name}")

        check("14건 목록 조회", len(client.get(prefix).json()) == 14)
        check("CK-03 상세 조회", client.get(f"{prefix}/CK-03").json()["rule_id"] == "CK-03")
        check("없는 CK는 404", client.get(f"{prefix}/CK-99").status_code == 404)
        with patch.dict(os.environ, {"AI10_DEV_API_ENABLED": "0"}):
            res = client.put(f"{prefix}/CK-03/text", json={"reviewer": "TEST", "text": "새 문장"})
            check("기본 쓰기 차단", res.status_code == 403)
        with patch.dict(os.environ, {"AI10_DEV_API_ENABLED": "1"}):
            res = client.post(f"{prefix}/CK-03/approve", json={"reviewer": "TEST", "note": "검토", "acknowledge_findings": False})
            check("경고 미확인 승인 거부", res.status_code == 400)
            res = client.put(f"{prefix}/CK-03/text", json={"reviewer": "TEST", "text": "점자블록 현장 확인 후 설치 필요성을 검토합니다."})
            check("수정 이력 저장", res.status_code == 200 and res.json()["revision"] == 1)
            res = client.post(f"{prefix}/CK-03/approve", json={"reviewer": "TEST", "note": "시험 승인", "acknowledge_findings": True, "evidence_source": "시험용 모의 근거(실제 원문 대조 아님)", "evidence_checked": True})
            check("명시적 승인", res.status_code == 200 and res.json()["approved"] is True)
            res = client.put(f"{prefix}/CK-03/text", json={"reviewer": "TEST", "text": "다른 문장"})
            check("승인 후 수정 차단", res.status_code == 409)
            res = client.post(f"{prefix}/CK-03/revoke", json={"reviewer": "TEST", "note": "시험 취소"})
            check("승인 취소 및 이력 유지", res.status_code == 200 and res.json()["approved"] is False and len(res.json()["events"]) == 3)
            res = client.post(f"{prefix}/CK-04/reject", json={"reviewer": "TEST", "note": "시험 반려"})
            check("반려 이력 저장", res.status_code == 200 and res.json()["review_status"] == "rejected")
    print(f"결과: {passed}/{passed} 통과 | 실제 JSON/DB 변경 없음")


if __name__ == "__main__":
    main()
