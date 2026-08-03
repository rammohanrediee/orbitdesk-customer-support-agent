import pytest

from orbitdesk_support_agent.sample_runner import (
    merge_output,
    select_samples,
)


SAMPLES = [
    {"question_id": "Q-001", "question": "First"},
    {"question_id": "Q-002", "question": "Second"},
]


def test_select_samples_returns_one_requested_case() -> None:
    assert select_samples(SAMPLES, "Q-002") == [SAMPLES[1]]


def test_select_samples_rejects_unknown_question_id() -> None:
    with pytest.raises(ValueError, match="Unknown question ID"):
        select_samples(SAMPLES, "Q-999")


def test_merge_output_replaces_existing_case_in_order() -> None:
    existing = [
        {"question_id": "Q-001", "response": "old"},
        {"question_id": "Q-002", "response": "keep"},
    ]
    replacement = {
        "question_id": "Q-001",
        "response": "new",
    }

    assert merge_output(existing, replacement) == [
        replacement,
        existing[1],
    ]


def test_merge_output_appends_new_case() -> None:
    existing = [{"question_id": "Q-001"}]
    new_output = {"question_id": "Q-002"}

    assert merge_output(existing, new_output) == [
        existing[0],
        new_output,
    ]
