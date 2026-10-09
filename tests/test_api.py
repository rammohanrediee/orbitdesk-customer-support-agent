from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from orbitdesk_support_agent.api import (
    SupportResult,
    _configured_retrieval_mode,
    app,
    build_runtime,
    validate_startup_config,
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
    assert response.json()["database_ready"] is True


def test_production_requires_database_and_provider(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_ENV", "production")
    monkeypatch.delenv("ORBITDESK_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ORBITDESK_DATABASE_URL"):
        validate_startup_config()


def test_production_rejects_demo_mode(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_ENV", "production")
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", "postgresql+psycopg://localhost/orbitdesk")
    monkeypatch.setenv("ORBITDESK_DEMO_MODE", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with pytest.raises(ValueError, match="DEMO_MODE"):
        validate_startup_config()


def test_production_requires_operator_token(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_ENV", "production")
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", "postgresql+psycopg://localhost/orbitdesk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORBITDESK_ALLOWED_ORIGINS", "https://example.test")
    monkeypatch.delenv("ORBITDESK_DEMO_MODE", raising=False)
    monkeypatch.delenv("ORBITDESK_OPERATOR_TOKEN", raising=False)
    with pytest.raises(ValueError, match="ORBITDESK_OPERATOR_TOKEN"):
        validate_startup_config()


def test_operator_token_protects_ticket_and_model_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_OPERATOR_TOKEN", "test-operator-secret")
    assert client.get("/api/health").json()["auth_required"] is True
    assert client.get("/api/tickets").status_code == 401
    assert client.post("/api/tickets", json={"question": "Who can create credentials?"}).status_code == 401
    assert client.post("/api/support", json={"question": "Who can create credentials?"}).status_code == 401
    assert client.get("/api/evidence/KB-005").status_code == 401
    assert client.get("/api/tickets", headers={"X-OrbitDesk-Token": "wrong"}).status_code == 401
    assert client.get("/api/tickets", headers={"X-OrbitDesk-Token": "test-operator-secret"}).status_code == 200


def test_operator_can_create_review_and_reopen_ticket(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_OPERATOR_TOKEN", "test-operator-secret")
    monkeypatch.setenv("ORBITDESK_DEMO_MODE", "1")
    monkeypatch.setenv("ORBITDESK_TICKET_DB", str(tmp_path / "private-demo.sqlite3"))
    headers = {"X-OrbitDesk-Token": "test-operator-secret"}
    question = client.get("/api/demo-questions").json()[1]["question"]

    created = client.post("/api/tickets", json={"question": question}, headers=headers)
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    reviewed = client.patch(
        f"/api/tickets/{ticket_id}/review",
        json={"action": "approve"},
        headers=headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    assert client.get(f"/api/tickets/{ticket_id}", headers=headers).json()["status"] == "approved"
    assert client.get(f"/api/tickets/{ticket_id}").status_code == 401


def test_production_requires_retention_policy(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_ENV", "production")
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", "postgresql+psycopg://localhost/orbitdesk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORBITDESK_ALLOWED_ORIGINS", "https://example.test")
    monkeypatch.setenv("ORBITDESK_OPERATOR_TOKEN", "a" * 24)
    monkeypatch.delenv("ORBITDESK_DEMO_MODE", raising=False)
    monkeypatch.delenv("ORBITDESK_RETENTION_DAYS", raising=False)
    with pytest.raises(ValueError, match="ORBITDESK_RETENTION_DAYS"):
        validate_startup_config()


def test_production_accepts_complete_operator_configuration(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_ENV", "production")
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", "postgresql+psycopg://localhost/orbitdesk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORBITDESK_ALLOWED_ORIGINS", "https://example.test")
    monkeypatch.setenv("ORBITDESK_OPERATOR_TOKEN", "a" * 24)
    monkeypatch.setenv("ORBITDESK_RETENTION_DAYS", "30")
    monkeypatch.delenv("ORBITDESK_DEMO_MODE", raising=False)
    validate_startup_config()


def test_health_reports_database_outage_without_error_details() -> None:
    with patch("orbitdesk_support_agent.api.ticket_store", side_effect=RuntimeError("secret connection text")):
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "secret connection text" not in response.text


def test_retrieval_mode_is_selected_by_server_configuration(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_RETRIEVAL_MODE", "semantic")

    assert _configured_retrieval_mode() == "semantic"


def test_runtime_is_built_once_per_retrieval_mode() -> None:
    build_runtime.cache_clear()
    with (
        patch("orbitdesk_support_agent.api.load_evidence_records", return_value=()),
        patch("orbitdesk_support_agent.api.KeywordRetriever") as retriever,
        patch("orbitdesk_support_agent.api.OpenRouterLanguageModel"),
        patch("orbitdesk_support_agent.api.build_graph"),
    ):
        first = build_runtime("keyword")
        second = build_runtime("keyword")
    build_runtime.cache_clear()

    assert first is second
    retriever.assert_called_once_with([])


def test_semantic_runtime_uses_the_semantic_retriever() -> None:
    build_runtime.cache_clear()
    records = ({"source_id": "KB-1", "source_type": "knowledge_base", "title": "One", "text": "One", "status": "current"},)
    with (
        patch("orbitdesk_support_agent.api.load_evidence_records", return_value=records),
        patch("orbitdesk_support_agent.semantic_retriever.SemanticRetriever") as retriever,
        patch("orbitdesk_support_agent.api.OpenRouterLanguageModel"),
        patch("orbitdesk_support_agent.api.build_graph"),
    ):
        build_runtime("semantic")
    build_runtime.cache_clear()

    retriever.assert_called_once_with(list(records))


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


def test_unexpected_workflow_error_is_logged_without_reaching_client() -> None:
    with (
        patch(
            "orbitdesk_support_agent.api.run_support_workflow",
            side_effect=RuntimeError("provider secret detail"),
        ),
        patch("orbitdesk_support_agent.api.logger.error") as log_error,
    ):
        response = client.post(
            "/api/support",
            json={"question": "Who can create an API credential?"},
        )

    assert response.status_code == 500
    assert "provider secret detail" not in response.text
    assert log_error.call_args.kwargs["extra"] == {
        "operation": "support",
        "error_type": "RuntimeError",
    }


def test_evidence_endpoint_opens_a_current_source() -> None:
    response = client.get("/api/evidence/KB-005")

    assert response.status_code == 200
    assert response.json()["source_id"] == "KB-005"
    assert "API Credentials" in response.json()["text"]


def test_evidence_endpoint_rejects_an_unknown_source() -> None:
    assert client.get("/api/evidence/UNKNOWN").status_code == 404


def test_demo_mode_runs_a_recorded_question_without_provider_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_DEMO_MODE", "1")
    monkeypatch.setenv("ORBITDESK_TICKET_DB", str(tmp_path / "demo.sqlite3"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    health = client.get("/api/health").json()
    assert health["status"] == "ready"
    assert health["demo_mode"] is True
    questions = client.get("/api/demo-questions").json()
    assert len(questions) == 5

    ticket = client.post("/api/tickets", json={"question": questions[1]["question"]})
    assert ticket.status_code == 201
    assert ticket.json()["generated_result"]["model"] == "recorded-demo"
    assert ticket.json()["generated_result"]["response"]["classification"] == "answerable"


def test_demo_mode_rejects_unrecorded_question(monkeypatch) -> None:
    monkeypatch.setenv("ORBITDESK_DEMO_MODE", "1")
    response = client.post("/api/tickets", json={"question": "This is not a recorded sample."})
    assert response.status_code == 422
