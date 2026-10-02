from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from orbitdesk_support_agent.retention import run_retention
from orbitdesk_support_agent.tickets import Ticket, TicketStore


def _result():
    return {
        "response": {
            "classification": "answerable",
            "answer": "Owners can manage the workspace.",
            "sources": [],
            "confidence": 0.8,
            "requires_human": False,
            "reason": "Documented rule.",
            "clarification_question": None,
            "warnings": [],
        },
        "execution_log": ["verify:passed"],
        "retrieval_mode": "keyword",
        "model": "test-model",
        "trace": {},
        "latency_seconds": 0.1,
    }


def test_retention_dry_run_preserves_data_and_apply_removes_only_old_reviewed(tmp_path):
    store = TicketStore(tmp_path / "retention.sqlite3")
    reviewed = store.create("Reviewed ticket", _result())
    pending = store.create("Pending ticket", _result())
    store.review(reviewed["id"], "approve", None, None)
    now = datetime.now(UTC)
    old = now - timedelta(days=40)
    with Session(store.engine) as session:
        session.execute(update(Ticket).values(updated_at=old))
        session.commit()

    preview = run_retention(store, days=30, apply=False, now=now)
    assert preview["eligible_count"] == 1
    assert preview["deleted_count"] == 0
    assert len(store.list_recent()) == 2

    applied = run_retention(store, days=30, apply=True, now=now)
    assert applied["deleted_count"] == 1
    assert [ticket["id"] for ticket in store.list_recent()] == [pending["id"]]
    with Session(store.engine) as session:
        assert session.scalar(text("SELECT COUNT(*) FROM decisions")) == 1
        assert session.scalar(text("SELECT COUNT(*) FROM reviews")) == 0


def test_retention_rejects_nonpositive_days(tmp_path):
    store = TicketStore(tmp_path / "retention.sqlite3")
    with pytest.raises(ValueError, match="positive"):
        run_retention(store, days=0, apply=False)
