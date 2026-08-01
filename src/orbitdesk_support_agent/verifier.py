from orbitdesk_support_agent.retriever import tokenize
from orbitdesk_support_agent.schemas import (
    EvidenceRecord,
    SupportResponse,
    VerificationResult,
)


def verify_response(
    response: SupportResponse,
    evidence: list[EvidenceRecord],) -> VerificationResult:
    issues: list[str] = []

    evidence_by_id = {
        record["source_id"]: record
        for record in evidence
    }

    if (
        not evidence
        and response.classification
        not in {
            "safe_failure",
            "out_of_scope",
            "requires_clarification",
        }
    ):
        issues.append(
            "The response classification requires supporting evidence."
        )

    if (
        response.classification
        in {"answerable", "requires_escalation"}
        and not response.sources
    ):
        issues.append(
            f"{response.classification} responses must cite a source."
        )

    if (
        response.classification == "requires_escalation"
        and not response.requires_human
    ):
        issues.append(
            "Escalation responses must set requires_human to true."
        )

    if (
        response.classification == "answerable"
        and response.requires_human
    ):
        issues.append(
            "Answerable responses must not require human escalation."
        )

    if response.classification == "requires_clarification":
        clarification = response.clarification_question

        if not clarification or not clarification.strip():
            issues.append(
                "Clarification responses must include a question."
            )

    for source in response.sources:
        record = evidence_by_id.get(source.source_id)

        if record is None:
            issues.append(
                f"Source {source.source_id} was not retrieved."
            )
            continue

        passage_tokens = tokenize(source.passage)
        evidence_tokens = tokenize(record["text"])

        if not passage_tokens:
            issues.append(
                f"Source {source.source_id} has an empty or "
                "uninformative passage."
            )
            continue

        if not passage_tokens & evidence_tokens:
            issues.append(
                f"The cited passage for {source.source_id} does not "
                "overlap with its retrieved evidence."
            )

    return VerificationResult(
        passed=not issues,
        issues=issues,
    )