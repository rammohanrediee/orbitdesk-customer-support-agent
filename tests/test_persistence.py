from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from orbitdesk_support_agent.api import SupportResult, app
from orbitdesk_support_agent.tickets import TicketStore


def generated_result() -> SupportResult:
    return SupportResult(
        response={
            "classification": "answerable",
            "answer": "Only Owners and Admins can create credentials.",
            "sources": [{
                "source_id": "KB-005",
                "passage": "Only Owners and Admins can create or revoke credentials.",
            }],
            "confidence": 0.8,
            "requires_human": False,
            "reason": "The KB documents this rule.",
            "reason_code": None,
            "clarification_question": None,
            "warnings": [],
        },
        execution_log=["triage", "retrieve:keyword", "generate", "verify:passed"],
        retrieval_mode="keyword",
        model="test-model",
        trace={"trace_id": "test-trace", "events": []},
        latency_seconds=0.1,
    )


def test_decision_and_citations_are_persisted_as_relational_records(tmp_path, monkeypatch):
    path = tmp_path / "tickets.sqlite3"
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", f"sqlite:///{path}")
    client = TestClient(app)

    with patch("orbitdesk_support_agent.api.run_support_workflow", return_value=generated_result()):
        created = client.post("/api/tickets", json={"question": "Who can create credentials?"})

    assert created.status_code == 201
    ticket_id = created.json()["id"]
    detail = client.get(f"/api/tickets/{ticket_id}/decision")
    assert detail.status_code == 200
    assert detail.json()["action"] == "ANSWER"
    assert detail.json()["reason"] == "The KB documents this rule."
    assert detail.json()["citations"][0]["source_title"] == "API Credentials"
    assert detail.json()["citations"][0]["source_type"] == "knowledge_base"

    engine = create_engine(f"sqlite:///{path}")
    columns = {column["name"] for column in inspect(engine).get_columns("decisions")}
    assert "generated_result" not in columns
    with Session(engine) as session:
        assert session.scalar(text("SELECT COUNT(*) FROM citations")) == 1


def test_review_stays_linked_to_ticket_and_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITDESK_DATABASE_URL", f"sqlite:///{tmp_path / 'tickets.sqlite3'}")
    client = TestClient(app)
    with patch("orbitdesk_support_agent.api.run_support_workflow", return_value=generated_result()):
        ticket_id = client.post("/api/tickets", json={"question": "Who can create credentials?"}).json()["id"]

    reviewed = client.patch(f"/api/tickets/{ticket_id}/review", json={"action": "edit", "answer": "Owners and Admins may create them."})
    assert reviewed.status_code == 200
    assert reviewed.json()["final_answer"] == "Owners and Admins may create them."
    assert client.get(f"/api/tickets/{ticket_id}/decision").json()["answer"] == generated_result().response["answer"]


def test_legacy_sqlite_is_preserved_and_rejected_with_clear_message(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE tickets (id TEXT PRIMARY KEY, generated_result TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO tickets VALUES ('old-1', '{}')"))

    with pytest.raises(ValueError, match="Legacy SQLite ticket database"):
        TicketStore(path)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM tickets")) == 1
