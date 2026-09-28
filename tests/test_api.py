from unittest.mock import patch

from fastapi.testclient import TestClient

from orbitdesk_support_agent.api import SupportResult, app


client = TestClient(app)


def test_health_reports_missing_provider_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "configuration_required"
    assert response.json()["api_key_configured"] is False


def test_support_rejects_short_questions() -> None:
    response = client.post(
        "/api/support",
        json={"question": "?", "retrieval": "keyword"},
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
                "retrieval": "keyword",
            },
        )

    assert response.status_code == 200
    assert response.json()["response"]["classification"] == "answerable"
    assert response.json()["trace"]["trace_id"] == "trace-test"
