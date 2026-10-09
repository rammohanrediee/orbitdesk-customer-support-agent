import json
from pathlib import Path

import pytest

from orbitdesk_support_agent.triage import triage_question


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UnexpectedLLM:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        raise AssertionError(
            "High-confidence sample routes should be deterministic."
        )


@pytest.mark.parametrize(
    ("question_id", "expected_classification"),
    [
        ("Q-001", "answerable"),
        ("Q-002", "answerable"),
        ("Q-003", "requires_clarification"),
        ("Q-004", "requires_escalation"),
        ("Q-005", "out_of_scope"),
    ],
)
def test_sample_question_has_expected_high_confidence_route(
    question_id: str,
    expected_classification: str,
) -> None:
    sample_data = json.loads(
        (PROJECT_ROOT / "sample_questions.json").read_text(
            encoding="utf-8"
        )
    )
    question = next(
        item["question"]
        for item in sample_data["questions"]
        if item["question_id"] == question_id
    )

    result = triage_question(question, UnexpectedLLM())

    assert result.classification == expected_classification


def test_vague_request_includes_clarification_question() -> None:
    result = triage_question(
        "Our data sync is not working. Can you tell me how to fix it?",
        UnexpectedLLM(),
    )

    assert result.classification == "requires_clarification"
    assert result.clarification_question


@pytest.mark.parametrize(
    ("question", "expected_classification", "expected_reason_code"),
    [
        ("Can support resend the exact export file nine days after delivery?", "answerable", None),
        ("Can support reveal a lost API credential secret?", "answerable", None),
        ("What is the Enterprise price and refund guarantee?", "requires_escalation", "INSUFFICIENT_EVIDENCE"),
        ("What uptime SLA does OrbitDesk promise in my contract?", "requires_escalation", "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_known_support_boundaries_route_without_model(
    question: str,
    expected_classification: str,
    expected_reason_code: str | None,
) -> None:
    result = triage_question(question, UnexpectedLLM())

    assert result.classification == expected_classification
    assert result.reason_code == expected_reason_code
