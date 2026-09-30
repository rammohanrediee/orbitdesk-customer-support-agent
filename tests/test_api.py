from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from orbitdesk_support_agent.api import (
    SupportResult,
    _configured_retrieval_mode,
    app,
)


client = TestClient(app)


def test_health_reports_missing_provider_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ORBITDESK_RETRIEVAL_MODE", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "configuration_required"
    assert response.json()["api_key_configured"] is False
    assert response.json()["retrieval_mode"] == "keyword"


def test_retrieval_mode_is_selected_by_server_configuration(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_RETRIEVAL_MODE", "semantic")

    assert _configured_retrieval_mode() == "semantic"


def test_invalid_retrieval_configuration_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_RETRIEVAL_MODE", "hybrid")

    with pytest.raises(ValueError, match="ORBITDESK_RETRIEVAL_MODE"):
        _configured_retrieval_mode()


def test_support_rejects_short_questions() -> None:
    response = client.post(
        "/api/support",
        json={"question": "?"},
    )

    assert response.status_code == 422


def test_support_rejects_client_retrieval_override() -> None:
    response = client.post(
        "/api/support",
        json={"question": "Who can create a credential?", "retrieval": "semantic"},
    )

    assert response.status_code == 422


def test_support_returns_grounded_workflow_result() -> None:
    result = SupportResult(
        response={
            "classification": "answerable",
            "answer": "Only Owners and Admins can create credentials.",
            "sources": [
                {
                    "source_id": "KB-005",
                    "passage": "Only Owners and Admins can create credentials.",
                }
            ],
            "confidence": 0.9,
            "requires_human": False,
            "reason": "Grounded in retrieved evidence.",
            "clarification_question": None,
            "warnings": [],
        },
        execution_log=["triage", "retrieve:keyword", "generate", "verify:passed"],
        retrieval_mode="keyword",
        model="z-ai/glm-4.5-air",
        trace={"trace_id": "trace-test", "events": []},
        latency_seconds=0.25,
    )

    with patch(
        "orbitdesk_support_agent.api.run_support_workflow",
        return_value=result,
    ):
        response = client.post(
            "/api/support",
            json={
                "question": "Who can create an API credential?",
            },
        )

    assert response.status_code == 200
    assert response.json()["response"]["classification"] == "answerable"
    assert response.json()["trace"]["trace_id"] == "trace-test"
