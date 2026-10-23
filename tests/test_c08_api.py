"""C-08 권한·응답 계약 시험. 실제 DB와 GitHub를 사용하지 않는다."""
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.c08_review_api import router
from app.core import access_audit
from app.core.auth import make_token
from app.core.responses import CamelCaseMiddleware, install_error_handlers
from app.services.c08.repository import get_repository


class FakeRepo:
    def __init__(self):
        self.reviews = []
        self.generated = []

    def run_scope(self, run_id):
        return {"run_id": run_id, "period_start": date(2026, 1, 1), "period_end": date(2026, 6, 30)} if run_id == 7 else None

    def has_complaints(self, run_id, gu=None):
        return True

    def type_options(self):
        return []

    def ensure_admin_samples(self, run_id):
        self.generated.append(run_id)

    def samples(self, run_id, scope, gu):
        return [{"sample_id": 11, "gu": "수정구", "sample_group": "AI 판단",
                 "masked_summary": "가린 민원 요약", "relevance": "보행안전 관련", "ped_type": None,
                 "class_reason": "보행 공간에 차가 있습니다.", "class_confidence": 0.8,
                 "done_result": None, "done_label": None}]

    def review(self, sample_id, user, result, relevance, ped_type, ip):
        self.reviews.append((sample_id, user["role"], result, relevance, ped_type, ip))

    def accuracy_strata(self, run_id, scope):
        if scope == "유형":
            return []
        return [{"gu": "수정구", "sample_group": "AI 판단", "population_count": 20,
                 "selected_count": 2, "checked_count": 2, "correct_count": 1}]

    def evaluation_rows(self, run_id, target):
        return [{"sample_id": 11, "review_scope": "전체 분류", "sample_group": "AI 판단",
                 "masked_summary": "가린 민원 요약", "after_relevance": "보행안전 관련", "after_ped_type": None}]


def client():
    repo = FakeRepo()
    app = FastAPI()
    app.add_middleware(CamelCaseMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app), repo


def header(role, gu=None):
    token, _ = make_token({"user_id": 1, "login_id": role, "role": role, "gu": gu})
    return {"Authorization": f"Bearer {token}"}


def test_operator_list_has_only_masked_fields_and_weighted_accuracy():
    c, repo = client()
    response = c.get("/api/c08/samples?runId=7", headers=header("operator"))
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["summary"] == "가린 민원 요약"
    assert data["items"][0]["keywords"] == "보행 공간에 차가 있습니다."
    assert data["items"][0]["relevance"] == "관련"
    assert data["items"][0]["confidence"] == 80
    assert "uploadId" not in data["items"][0]
    assert "raw" not in str(data).lower()
    assert "location" not in str(data).lower()
    assert repo.generated == [7]
    result = c.get("/api/c08/accuracy?runId=7", headers=header("operator")).json()
    assert result["relevance"]["accuracy"] == 0.5
    assert result["type"]["status"] == "no_data"


def test_old_upload_filter_is_rejected_instead_of_ignored():
    c, _ = client()
    assert c.get("/api/c08/samples?runId=7&uploadId=2", headers=header("operator")).status_code == 422
    assert c.get("/api/c08/accuracy?runId=7&uploadId=2", headers=header("operator")).status_code == 422


def test_district_scope_and_city_rejection():
    c, repo = client()
    own = c.get("/api/c08/samples?runId=7&gu=수정구", headers=header("district", "수정구"))
    assert own.status_code == 200 and own.json()["items"] == []
    assert own.json()["labels"] == []
    assert c.get("/api/c08/samples?runId=7&gu=분당구", headers=header("district", "수정구")).status_code == 403
    assert c.get("/api/c08/samples?runId=7", headers=header("city")).status_code == 403
    assert c.get("/api/c08/accuracy?runId=7", headers=header("district", "수정구")).status_code == 403
    assert repo.generated == [7]


def test_review_rejects_district_relevance_and_accepts_operator_change():
    c, repo = client()
    denied = c.post("/api/c08/samples/11/review", json={"result": "고침", "relevance": "비관련"},
                    headers=header("district", "수정구"))
    assert denied.status_code == 403
    assert repo.reviews == []
    changed = c.post("/api/c08/samples/11/review", json={"result": "고침", "relevance": "비관련"},
                     headers=header("operator"))
    assert changed.status_code == 200
    assert repo.reviews[0][3] == "비관련"


def test_evaluation_export_uses_masked_summary_and_logs_download(monkeypatch):
    c, _ = client()
    audits = []
    monkeypatch.setattr(access_audit, "record", lambda *a, **kw: audits.append((a, kw)))
    response = c.get("/api/c08/evaluation?runId=7", headers=header("operator"))
    assert response.status_code == 200
    assert "가린 민원 요약" in response.text
    assert "보행안전 관련" in response.text
    assert "원문" not in response.text
    assert len(audits) == 1 and audits[0][0][2] == access_audit.DOWNLOAD
