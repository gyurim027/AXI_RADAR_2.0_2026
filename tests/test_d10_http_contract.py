"""D-10 HTTP contract checks using FastAPI TestClient and an in-memory SQL stub.

Run in the RADAR repo: uv run python -m pytest tests/test_d10_http_contract.py -q
No live MySQL connection or DB writes. The actual workflow implementation is exercised.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import db
from app.core.auth import make_token
from app.main import app
from app.services.priority import repository as priority_repository
from app.api import d10_run_read_api as d10_api


RUN_IDS = (1, 2, 3, 4, 5)


def auth(role: str) -> dict[str, str]:
    token, _ = make_token({"user_id": 9, "login_id": role, "role": role, "gu": None})
    return {"Authorization": f"Bearer {token}"}


class FakeWorkflowDB:
    def __init__(self):
        self.saved = {
            3: {"run_name": "2027 정기", "run_kind": "연간", "run_status": "검토 중", "opened_at": datetime(2026, 11, 3, 8)},
            4: {"run_name": "산정 중 회차", "run_kind": "연간", "run_status": "산정 중", "opened_at": datetime(2026, 11, 3, 8)},
            5: {"run_name": "상반기 참고", "run_kind": "반기 참고", "run_status": "참고", "opened_at": datetime(2026, 11, 3, 8)},
        }
        self.events = []
        self.commits = 0
        self.ready = True

    def read_only(self, sql, args=()):
        if "information_schema.TABLES" in sql:
            return [{"n": 2 if self.ready else 0}]
        if "FROM radar_run_workflow" in sql:
            return [
                {"run_id": rid, **row}
                for rid, row in self.saved.items() if rid in set(args)
            ]
        raise AssertionError(f"Unexpected DB read: {sql}")

    def connect(self):
        return _FakeConnection(self)


class _FakeConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        return False

    def cursor(self):
        return _FakeCursor(self.state)

    def commit(self):
        self.state.commits += 1


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        return False

    def execute(self, sql, args=()):
        if "FROM priority_run" in sql and "FOR UPDATE" in sql:
            self.value = {"run_id": args[0]} if args[0] in RUN_IDS else None
        elif "FROM radar_run_workflow" in sql and "FOR UPDATE" in sql:
            self.value = self.state.saved.get(args[0])
        elif "COUNT(*) AS candidate_count" in sql:
            self.value = {"candidate_count": 2, "scored_count": 2}
        elif "SELECT NOW(6)" in sql:
            self.value = {"now_value": datetime(2026, 11, 3, 9)}
        elif "INSERT INTO radar_run_workflow" in sql:
            rid, name, kind, status, opened_at, actor = args
            if rid in self.state.saved:
                raise AssertionError("Duplicate workflow INSERT")
            self.state.saved[rid] = {
                "run_name": name, "run_kind": kind,
                "run_status": status, "opened_at": opened_at,
            }
        elif "INSERT INTO radar_run_status_event" in sql:
            self.state.events.append(args)
        else:
            raise AssertionError(f"Unexpected DB write: {sql}")

    def fetchone(self):
        return self.value


class FakePriorityRepo(priority_repository.PriorityRepository):
    def list_runs(self, limit):
        return [
            {"run_id": rid, "build_id": f"B{rid}", "rule_version": "TEST",
             "created_at": datetime(2026, 11, 3, 7), "note": None,
             "candidate_cnt": 2, "selected_cnt": 1, "scored_cnt": 2}
            for rid in RUN_IDS[:limit]
        ]

    def get_run(self, run_id):
        return next((x for x in self.list_runs(10) if x["run_id"] == run_id), None)


@pytest.fixture
def api_client():
    state = FakeWorkflowDB()
    previous = priority_repository.get_repository()
    priority_repository.set_repository(FakePriorityRepo())
    with patch.object(db, "read_only", side_effect=state.read_only), patch.object(db, "connect", side_effect=state.connect), patch.object(d10_api._repo, "list_runs", side_effect=lambda limit: FakePriorityRepo().list_runs(limit)):
        try:
            yield TestClient(app), state
        finally:
            priority_repository.set_repository(previous)


def _ids(response):
    assert response.status_code == 200, response.text
    return [int(row.get("runId", row.get("run_id"))) for row in response.json()["runs"]]


def test_http_visible_runs_nonoperator_fail_closed(api_client):
    client, _state = api_client
    response = client.get("/api/priority/runs", headers=auth("city"))
    # Existing contract preserves legacy run 1 for read-only listing.
    # Unknown status run 2 and processing run 4 must stay hidden.
    assert _ids(response) == [1, 3, 5]


def test_http_visible_runs_operator_can_inspect_unopened(api_client):
    client, _state = api_client
    response = client.get("/api/d10/runs", headers=auth("operator"))
    assert _ids(response) == [1, 2, 3, 4, 5]
    assert response.json()["readOnly"] is True


def test_http_open_retry_is_noop_and_conflicting_reopen_fails(api_client):
    client, state = api_client
    endpoint = "/api/d10/runs/2/open"
    payload = {"name": "2027 정기 회차", "kind": "연간"}

    assert client.post(endpoint, json=payload).status_code == 401
    assert client.post(endpoint, headers=auth("city"), json=payload).status_code == 403

    first = client.post(endpoint, headers=auth("operator"), json=payload)
    assert first.status_code == 200, first.text
    assert "alreadyOpen" in first.json().get("run", {}), (
        f"HTTP open response omits alreadyOpen: {first.json()!r}; "
        "inspect registered /api/d10/runs/{run_id}/open route"
    )
    assert first.json()["run"]["alreadyOpen"] is False
    assert state.commits == 1
    assert len(state.events) == 1

    second = client.post(endpoint, headers=auth("operator"), json=payload)
    assert second.status_code == 200, second.text
    assert "alreadyOpen" in second.json().get("run", {}), (
        f"HTTP replay response omits alreadyOpen: {second.json()!r}"
    )
    assert second.json()["run"]["alreadyOpen"] is True
    assert state.commits == 1, "Identical retry must not commit again"
    assert len(state.events) == 1, "Identical retry must not write a second event"

    changed = client.post(endpoint, headers=auth("operator"), json={"name": "변경된 회차", "kind": "연간"})
    assert changed.status_code == 409, changed.text
    assert state.commits == 1
    assert len(state.events) == 1


def test_http_open_fails_closed_without_schema(api_client):
    client, state = api_client
    state.ready = False
    response = client.post("/api/d10/runs/2/open", headers=auth("operator"), json={"name": "2027 정기", "kind": "연간"})
    assert response.status_code == 503, response.text
    assert state.commits == 0
    assert state.events == []


def test_http_open_excludes_prototype_run_one(api_client):
    client, state = api_client
    response = client.post("/api/d10/runs/1/open", headers=auth("operator"), json={"name": "과거 회차", "kind": "연간"})
    assert response.status_code == 422, response.text
    assert state.commits == 0
    assert state.events == []
