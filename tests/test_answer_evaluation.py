from orbitdesk_support_agent.answer_evaluation import AnswerCase, evaluate_answers
from orbitdesk_support_agent.answer_evaluation import load_answer_cases
from pathlib import Path


def output(case_id, classification, answer, sources, requires_human=False):
    return {
        "question_id": case_id,
        "response": {
            "classification": classification,
            "answer": answer,
            "sources": sources,
            "confidence": 0.8,
            "requires_human": requires_human,
            "reason": "Documented behavior.",
            "clarification_question": None,
            "warnings": [],
        },
    }


def test_answer_report_checks_route_evidence_and_required_facts():
    cases = [
        AnswerCase("Q-1", "answerable", False, ("KB-1",), ("owners",)),
        AnswerCase("Q-2", "requires_escalation", True, ("KB-2",), ("escalate",)),
    ]
    outputs = [
        output("Q-1", "answerable", "Owners can do this.", [{"source_id": "KB-1", "passage": "Owners can do this."}]),
        output("Q-2", "answerable", "Try again.", [{"source_id": "KB-2", "passage": "Try again."}]),
    ]
    records = [
        {"source_id": "KB-1", "text": "Owners can do this.", "source_type": "knowledge_base", "title": "One", "status": "current"},
        {"source_id": "KB-2", "text": "Escalate after retry.", "source_type": "knowledge_base", "title": "Two", "status": "current"},
    ]

    report = evaluate_answers(cases, outputs, records)

    assert report["case_count"] == 2
    assert report["passed_count"] == 1
    assert report["pass_rate"] == 0.5
    assert report["answer_correctness_counts"] == {"correct": 1, "answerable_evaluated": 1}
    assert report["grounded_response_counts"] == {"grounded": 1, "answered": 2}
    assert report["results"][1]["passed"] is False
    assert "classification" in report["results"][1]["issues"]
    assert "citation_excerpt" in report["results"][1]["issues"]


def test_missing_output_is_reported_as_a_failure():
    case = AnswerCase("Q-1", "out_of_scope", False, (), ())
    report = evaluate_answers([case], [], [])
    assert report["results"][0]["issues"] == ["missing_output"]
    assert report["evaluated_count"] == 0
    assert report["missing_count"] == 1


def test_duplicate_output_ids_are_rejected():
    case = AnswerCase("Q-1", "out_of_scope", False, (), ())
    result = output("Q-1", "out_of_scope", "No", [])
    try:
        evaluate_answers([case], [result, result], [])
    except ValueError as error:
        assert "Duplicate" in str(error)
    else:
        raise AssertionError("duplicate IDs were accepted")


def test_escalation_metrics_use_only_evaluated_cases():
    cases = [
        AnswerCase("Q-1", "requires_escalation", True, (), ()),
        AnswerCase("Q-2", "answerable", False, (), ()),
        AnswerCase("Q-3", "requires_escalation", True, (), ()),
    ]
    outputs = [
        output("Q-1", "requires_escalation", "Escalate safely.", [], True),
        output("Q-2", "requires_escalation", "Escalate safely.", [], True),
    ]
    report = evaluate_answers(cases, outputs, [])
    assert report["evaluated_count"] == 2
    assert report["missing_count"] == 1
    assert report["escalation_precision"] == 0.5
    assert report["escalation_recall"] == 1.0
    assert report["escalation_counts"]["expected_escalations_evaluated"] == 1


def test_fixed_quality_dataset_has_30_distinct_cases():
    path = Path(__file__).resolve().parents[1] / "answer_eval.json"
    cases = load_answer_cases(path)
    assert len(cases) == 30
    assert len({case.question_id for case in cases}) == 30
    assert all(case.question for case in cases)


def test_invalid_saved_output_counts_as_failed_answer_and_missed_escalation():
    cases = [
        AnswerCase("A", "answerable", False, (), ()),
        AnswerCase("E", "requires_escalation", True, (), ()),
    ]
    report = evaluate_answers(cases, [{"question_id": "A", "error_type": "TimeoutError"}, {"question_id": "E", "error_type": "TimeoutError"}], [])
    assert report["invalid_response_count"] == 2
    assert report["answer_correctness"] == 0.0
    assert report["escalation_recall"] == 0.0


def test_equivalent_term_and_linked_case_source_are_accepted():
    case = AnswerCase("Q-1", "answerable", False, ("KB-1",), ("resave",))
    outputs = [output(
        "Q-1",
        "answerable",
        "Save the schedule.",
        [{"source_id": "CASE-1", "passage": "Save the schedule."}],
    )]
    records = [{
        "source_id": "CASE-1",
        "text": "Save the schedule.",
        "source_type": "resolved_case",
        "title": "Saved schedule",
        "status": "resolved",
        "source_documents": ["KB-1"],
    }]

    assert evaluate_answers([case], outputs, records)["passed_count"] == 1
