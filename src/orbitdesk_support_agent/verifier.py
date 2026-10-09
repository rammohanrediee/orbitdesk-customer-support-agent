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
        and response.reason_code not in {"INSUFFICIENT_EVIDENCE", "CONFLICTING_SOURCES"}
    ):
        issues.append(
            "MISSING_EVIDENCE: The response classification requires supporting evidence."
        )

    if (
        response.classification
        in {"answerable", "requires_escalation"}
        and not response.sources
        and response.reason_code not in {"INSUFFICIENT_EVIDENCE", "CONFLICTING_SOURCES"}
    ):
        issues.append(
            f"MISSING_CITATION: {response.classification} responses must cite a source."
        )

    if (
        response.classification == "requires_escalation"
        and not response.requires_human
    ):
        issues.append(
            "INVALID_HUMAN_FLAG: Escalation responses must set requires_human to true."
        )

    if (
        response.classification == "answerable"
        and response.requires_human
    ):
        issues.append(
            "INVALID_HUMAN_FLAG: Answerable responses must not require human escalation."
        )

    if response.classification == "requires_clarification":
        clarification = response.clarification_question

        if not clarification or not clarification.strip():
            issues.append(
                "MISSING_CLARIFICATION: Clarification responses must include a question."
            )

    for source in response.sources:
        record = evidence_by_id.get(source.source_id)

        if record is None:
            issues.append(
                f"UNKNOWN_SOURCE: Source {source.source_id} was not retrieved."
            )
            continue

        if record["status"] == "superseded":
            issues.append(f"SUPERSEDED_SOURCE: Source {source.source_id} is superseded.")
            continue

        passage_tokens = tokenize(source.passage)
        if not passage_tokens:
            issues.append(
                f"EMPTY_PASSAGE: Source {source.source_id} has an empty or "
                "uninformative passage."
            )
            continue

        normalized_passage = " ".join(source.passage.split())
        normalized_evidence = " ".join(record["text"].split())
        if normalized_passage not in normalized_evidence:
            issues.append(
                f"INVALID_PASSAGE: The cited passage for {source.source_id} is not an "
                "exact excerpt of its retrieved evidence."
            )

        if source.claim and " ".join(source.claim.split()) not in " ".join(response.answer.split()):
            issues.append(
                f"CLAIM_NOT_IN_ANSWER: The claim linked to {source.source_id} is not in the answer."
            )

    return VerificationResult(
        passed=not issues,
        issues=issues,
    )
