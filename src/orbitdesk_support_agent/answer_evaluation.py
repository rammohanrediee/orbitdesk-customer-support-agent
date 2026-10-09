"""Repeatable checks for saved support answers.

These checks cover known facts and routing rules; they are not a substitute for
human assessment of answer quality.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

from orbitdesk_support_agent.schemas import EvidenceRecord, SupportResponse
from orbitdesk_support_agent.verifier import verify_response


TERM_ALIASES = {"resave": ("resave", "save")}


@dataclass(frozen=True)
class AnswerCase:
    question_id: str
    expected_classification: str
    expected_requires_human: bool
    required_source_ids: tuple[str, ...]
    required_answer_terms: tuple[str, ...]
    question: str = ""
    expected_action: str | None = None
    expected_reason_code: str | None = None
    forbidden_answer_terms: tuple[str, ...] = ()


def action_for_classification(classification: str) -> str:
    return {
        "answerable": "ANSWER",
        "requires_escalation": "ESCALATE",
        "requires_clarification": "CLARIFY",
    }.get(classification, "SAFE_FAILURE")


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def evaluate_answers(
    cases: Sequence[AnswerCase],
    outputs: list[dict[str, Any]],
    records: list[EvidenceRecord],
) -> dict[str, Any]:
    if not cases:
        raise ValueError("Answer evaluation requires at least one case.")
    by_id: dict[str, dict[str, Any]] = {}
    for output in outputs:
        question_id = output["question_id"]
        if question_id in by_id:
            raise ValueError(f"Duplicate output ID: {question_id}")
        by_id[question_id] = output

    records_by_id = {record["source_id"]: record for record in records}
    results = []
    escalation_true_positive = 0
    escalation_false_positive = 0
    escalation_false_negative = 0
    answerable_count = 0
    correct_answer_count = 0
    answered_count = 0
    grounded_answer_count = 0
    unsupported_answer_count = 0
    for case in cases:
        output = by_id.get(case.question_id)
        if output is None:
            results.append({"question_id": case.question_id, "passed": False, "issues": ["missing_output"]})
            continue

        expected_action = case.expected_action or action_for_classification(case.expected_classification)
        if expected_action == "ANSWER":
            answerable_count += 1

        try:
            response = SupportResponse.model_validate(output["response"])
        except (ValueError, KeyError):
            if expected_action == "ESCALATE":
                escalation_false_negative += 1
            results.append({"question_id": case.question_id, "passed": False, "issues": ["invalid_response"]})
            continue

        issues = []
        actual_action = action_for_classification(response.classification)
        if response.classification != case.expected_classification:
            issues.append("classification")
        if actual_action != expected_action:
            issues.append("action")
        if response.requires_human != case.expected_requires_human:
            issues.append("human_review")
        if case.expected_reason_code and response.reason_code != case.expected_reason_code:
            issues.append("reason_code")
        source_ids = {source.source_id for source in response.sources}
        supported_source_ids = source_ids | {
            linked_id
            for source_id in source_ids
            for linked_id in records_by_id.get(source_id, {}).get("source_documents", [])
        }
        if not set(case.required_source_ids).issubset(supported_source_ids):
            issues.append("required_sources")
        answer = response.answer.casefold()
        if any(
            not any(alias in answer for alias in TERM_ALIASES.get(term.casefold(), (term.casefold(),)))
            for term in case.required_answer_terms
        ):
            issues.append("required_answer_terms")
        if any(term.casefold() in answer for term in case.forbidden_answer_terms):
            issues.append("forbidden_answer_terms")

        cited_records = [records_by_id[source_id] for source_id in source_ids if source_id in records_by_id]
        if not verify_response(response, cited_records).passed:
            issues.append("citation_excerpt")
        if expected_action == "ESCALATE" and actual_action == "ESCALATE":
            escalation_true_positive += 1
        elif expected_action != "ESCALATE" and actual_action == "ESCALATE":
            escalation_false_positive += 1
        elif expected_action == "ESCALATE":
            escalation_false_negative += 1

        if expected_action == "ANSWER":
            if actual_action == "ANSWER" and not any(
                issue in issues for issue in ("required_answer_terms", "forbidden_answer_terms")
            ):
                correct_answer_count += 1
        if actual_action == "ANSWER":
            answered_count += 1
            if not any(issue in issues for issue in ("required_sources", "citation_excerpt")):
                grounded_answer_count += 1
            if any(issue in issues for issue in ("required_sources", "citation_excerpt", "forbidden_answer_terms")):
                unsupported_answer_count += 1

        results.append({
            "question_id": case.question_id,
            "expected_action": expected_action,
            "actual_action": actual_action,
            "passed": not issues,
            "issues": issues,
        })

    passed_count = sum(result["passed"] for result in results)
    evaluated_count = len(cases) - sum("missing_output" in result["issues"] for result in results)
    invalid_count = sum("invalid_response" in result["issues"] for result in results)
    return {
        "case_count": len(cases),
        "evaluated_count": evaluated_count,
        "missing_count": len(cases) - evaluated_count,
        "invalid_response_count": invalid_count,
        "passed_count": passed_count,
        "pass_rate": _rate(passed_count, evaluated_count),
        "answer_correctness": _rate(correct_answer_count, answerable_count),
        "answer_correctness_counts": {
            "correct": correct_answer_count,
            "answerable_evaluated": answerable_count,
        },
        "grounded_response_rate": _rate(grounded_answer_count, answered_count),
        "grounded_response_counts": {"grounded": grounded_answer_count, "answered": answered_count},
        "unsupported_answer_rate": _rate(unsupported_answer_count, answered_count),
        "unsupported_answer_counts": {"unsupported_proxy": unsupported_answer_count, "answered": answered_count},
        "escalation_precision": _rate(
            escalation_true_positive,
            escalation_true_positive + escalation_false_positive,
        ),
        "escalation_recall": _rate(
            escalation_true_positive,
            escalation_true_positive + escalation_false_negative,
        ),
        "escalation_counts": {
            "true_positive": escalation_true_positive,
            "false_positive": escalation_false_positive,
            "false_negative": escalation_false_negative,
            "expected_escalations_evaluated": escalation_true_positive + escalation_false_negative,
            "predicted_escalations_evaluated": escalation_true_positive + escalation_false_positive,
        },
        "results": results,
    }


def load_answer_cases(path: Path) -> list[AnswerCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        AnswerCase(
            question_id=item["question_id"],
            expected_classification=item["expected_classification"],
            expected_requires_human=item["expected_requires_human"],
            required_source_ids=tuple(item.get("required_source_ids", [])),
            required_answer_terms=tuple(item.get("required_answer_terms", [])),
            question=item.get("question", ""),
            expected_action=item.get("expected_action"),
            expected_reason_code=item.get("expected_reason_code"),
            forbidden_answer_terms=tuple(item.get("forbidden_answer_terms", [])),
        )
        for item in data["cases"]
    ]
    ids = [case.question_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique.")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate saved support answers against labeled expectations.")
    parser.add_argument("--outputs", type=Path, default=Path("sample_outputs.json"))
    parser.add_argument("--labels", type=Path, default=Path("answer_eval.json"))
    arguments = parser.parse_args()

    from orbitdesk_support_agent.indexer import build_evidence_records
    from orbitdesk_support_agent.loader import load_knowledge_base, load_resolved_cases

    project_root = Path(__file__).resolve().parents[2]
    records = build_evidence_records(
        load_knowledge_base(project_root / "knowledge_base"),
        load_resolved_cases(project_root / "resolved_cases.json"),
    )
    outputs = json.loads(arguments.outputs.read_text(encoding="utf-8"))
    report = evaluate_answers(load_answer_cases(arguments.labels), outputs, records)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
