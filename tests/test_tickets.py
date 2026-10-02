from unittest.mock import patch

from fastapi.testclient import TestClient

from orbitdesk_support_agent.api import SupportResult, app


def sample_result() -> SupportResult:
    return SupportResult(
        response={
            "classification": "answerable",
            "answer": "Owners can create credentials.",
            "sources": [{"source_id": "KB-005", "passage": "Owners can create credentials."}],
            "confidence": 0.8,
            "requires_human": False,
            "reason": "The source covers this question.",
            "clarification_question": None,
            "warnings": [],
        },
        execution_log=["triage", "retrieve:keyword", "verify:passed"],
        retrieval_mode="keyword",
        model="test-model",
        trace={"trace_id": "trace-test", "events": []},
        latency_seconds=0.1,
    )


def test_created_ticket_survives_a_new_request_and_can_be_reviewed(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITDESK_TICKET_DB", str(tmp_path / "tickets.sqlite3"))
    client = TestClient(app)

    with patch("orbitdesk_support_agent.api.run_support_workflow", return_value=sample_result()):
        created = client.post("/api/tickets", json={"question": "Who creates credentials?"})

    assert created.status_code == 201
    ticket = created.json()
    assert ticket["status"] == "pending"
    assert ticket["generated_result"]["response"]["answer"] == "Owners can create credentials."
    assert ticket["final_answer"] is None

    ticket_id = ticket["id"]
    assert client.get("/api/tickets").json()[0]["id"] == ticket_id
    assert client.get(f"/api/tickets/{ticket_id}").json()["question"] == "Who creates credentials?"

    reviewed = client.patch(f"/api/tickets/{ticket_id}/review", json={"action": "approve"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["final_answer"] == "Owners can create credentials."
    assert client.get(f"/api/tickets/{ticket_id}").json()["status"] == "approved"


def test_edit_requires_a_new_answer_and_closes_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITDESK_TICKET_DB", str(tmp_path / "tickets.sqlite3"))
    client = TestClient(app)
    with patch("orbitdesk_support_agent.api.run_support_workflow", return_value=sample_result()):
        ticket_id = client.post("/api/tickets", json={"question": "Who creates credentials?"}).json()["id"]

    assert client.patch(f"/api/tickets/{ticket_id}/review", json={"action": "edit"}).status_code == 422
    edited = client.patch(
        f"/api/tickets/{ticket_id}/review",
        json={"action": "edit", "answer": "Owners and Admins can create credentials."},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "edited"
    assert edited.json()["final_answer"] == "Owners and Admins can create credentials."
    assert client.patch(f"/api/tickets/{ticket_id}/review", json={"action": "approve"}).status_code == 409


def test_escalation_requires_a_note_and_missing_ticket_is_404(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITDESK_TICKET_DB", str(tmp_path / "tickets.sqlite3"))
    client = TestClient(app)
    with patch("orbitdesk_support_agent.api.run_support_workflow", return_value=sample_result()):
        ticket_id = client.post("/api/tickets", json={"question": "Who creates credentials?"}).json()["id"]

    assert client.patch(f"/api/tickets/{ticket_id}/review", json={"action": "escalate"}).status_code == 422
    escalated = client.patch(
        f"/api/tickets/{ticket_id}/review",
        json={"action": "escalate", "note": "Needs security team review."},
    )
    assert escalated.status_code == 200
    assert escalated.json()["status"] == "escalated"
    assert escalated.json()["review_note"] == "Needs security team review."
    assert client.get("/api/tickets/unknown").status_code == 404
