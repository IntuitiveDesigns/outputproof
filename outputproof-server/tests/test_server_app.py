# Copyright 2026 StreamKernel LLC
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE for details.

"""Tests for the OutputProof dashboard server package."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from outputproof_server.app import create_app


def make_client(tmp_path):
    return TestClient(create_app(database_path=tmp_path / "outputproof-server.db"))


def test_health_check(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_redirects_to_dashboard(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/dashboard"


def test_api_status(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "name": "OutputProof Dashboard",
        "version": "1.1.0",
        "status": "running",
    }


def test_create_and_list_verification(tmp_path):
    client = make_client(tmp_path)
    payload = {
        "request_id": "req-1",
        "agent_id": "agent-1",
        "verdict": "PASS",
        "confidence_score": 0.95,
        "assertion_results": [],
    }

    create_response = client.post("/api/verifications", json=payload)
    list_response = client.get("/api/verifications")

    assert create_response.status_code == 200
    assert create_response.json() == {"status": "created", "id": "req-1"}
    assert list_response.status_code == 200
    result = list_response.json()["results"][0]
    timestamp = datetime.fromisoformat(result["timestamp"])

    assert result["request_id"] == "req-1"
    assert timestamp.tzinfo == timezone.utc


def test_failure_listing_accepts_legacy_naive_timestamps(tmp_path):
    client = make_client(tmp_path)
    payload = {
        "request_id": "req-legacy",
        "agent_id": "agent-1",
        "verdict": "FAIL",
        "confidence_score": 0.25,
        "assertion_results": [],
        "timestamp": datetime.now().isoformat(),
    }

    create_response = client.post("/api/verifications", json=payload)
    failures_response = client.get("/api/failures")

    assert create_response.status_code == 200
    assert failures_response.status_code == 200
    assert failures_response.json()[0]["request_id"] == "req-legacy"


def test_verifications_persist_to_sqlite(tmp_path):
    database_path = tmp_path / "outputproof-server.db"
    first_client = TestClient(create_app(database_path=database_path))
    payload = {
        "request_id": "req-persisted",
        "agent_id": "agent-1",
        "verdict": "PASS",
        "confidence_score": 0.9,
        "assertion_results": [],
    }

    create_response = first_client.post("/api/verifications", json=payload)
    second_client = TestClient(create_app(database_path=database_path))
    get_response = second_client.get("/api/verifications/req-persisted")

    assert create_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["request_id"] == "req-persisted"


def test_team_reliability_leaderboard_groups_metadata(tmp_path):
    client = make_client(tmp_path)
    payloads = [
        {
            "request_id": "req-dev-pass",
            "agent_id": "agent-a",
            "verdict": "PASS",
            "confidence_score": 0.95,
            "assertion_results": [],
            "metadata": {"developer_id": "dev-a", "task_type": "auth"},
        },
        {
            "request_id": "req-dev-fail",
            "agent_id": "agent-b",
            "verdict": "FAIL",
            "confidence_score": 0.2,
            "assertion_results": [],
            "metadata": {"developer_id": "dev-b", "task_type": "auth"},
        },
        {
            "request_id": "req-dev-partial",
            "agent_id": "agent-b",
            "verdict": "PARTIAL",
            "confidence_score": 0.5,
            "assertion_results": [],
            "metadata": {"developer_id": "dev-b", "task_type": "tests"},
        },
    ]

    for payload in payloads:
        response = client.post("/api/verifications", json=payload)
        assert response.status_code == 200

    developer_response = client.get("/api/leaderboard?dimension=developer&days=30")
    task_response = client.get("/api/leaderboard?dimension=task_type&days=30")

    assert developer_response.status_code == 200
    developers = developer_response.json()
    assert developers[0]["name"] == "dev-b"
    assert developers[0]["pass_rate"] == 0
    assert developers[0]["failed"] == 1
    assert developers[0]["partial"] == 1

    assert task_response.status_code == 200
    tasks = task_response.json()
    assert tasks[0]["name"] == "tests"
    assert tasks[0]["pass_rate"] == 0


def test_leaderboard_rejects_unknown_dimension(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/leaderboard?dimension=repository")

    assert response.status_code == 400
