import json
from typing import Any, Protocol

from orbitdesk_support_agent.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from orbitdesk_support_agent.schemas import (
    Classification,
    EvidenceRecord,
    GeneratedAnswer,
    SupportResponse,
)


class LanguageModel(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        ...


def extract_json_object(raw_text: str) -> dict[str, Any]:
    start = raw_text.find("{")
    end = raw_text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "The model response did not contain a JSON object."
        )

    json_text = raw_text[start : end + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The model returned invalid JSON."
        ) from error

    if not isinstance(parsed, dict):
        raise ValueError(
            "The generated JSON must be an object."
        )

    return parsed


def generate_response(
    question: str,
    records: list[EvidenceRecord],
    llm: LanguageModel,
    expected_classification: Classification = "answerable",
    revision_feedback: list[str] | None = None,
) -> SupportResponse:
    if not records:
        return SupportResponse(
            classification="requires_escalation",
            answer=(
                "I could not find enough OrbitDesk documentation to answer "
                "this safely. A support specialist needs to review it."
            ),
            sources=[],
            confidence=0.0,
            requires_human=True,
            reason="No relevant evidence was retrieved.",
            reason_code="INSUFFICIENT_EVIDENCE",
            clarification_question=None,
            warnings=["No answer was generated without evidence."],
        )

    output_schema = json.dumps(
        GeneratedAnswer.model_json_schema(),
        indent=2,
    )
    user_prompt = build_user_prompt(question, records)
    user_prompt = (
        f"{user_prompt}\n\n"
        f"The workflow classification is {expected_classification}.\n"
        "Return only one JSON object matching this schema:\n"
        f"{output_schema}\n\n"
        "Keep the answer under 100 words. Every citation passage must "
        "be copied exactly from the cited evidence. Give only "
        "instructions supported by those exact excerpts. For each citation, "
        "include a claim copied exactly from the answer that the passage supports."
    )

    if revision_feedback:
        feedback = "; ".join(revision_feedback)
        user_prompt += (
            "\n\nThe previous attempt failed verification. Correct "
            f"these issues: {feedback}"
        )

    raw_response = llm.generate(
        SYSTEM_PROMPT,
        user_prompt,
    )
    parsed_response = extract_json_object(raw_response)
    generated = GeneratedAnswer.model_validate(parsed_response)
    retrieved_by_id = {record["source_id"]: record for record in records}
    for citation in generated.citations:
        if citation.source_id not in retrieved_by_id:
            raise ValueError(
                f"Cited source {citation.source_id} was not retrieved."
            )

    enriched_citations = [
        citation.model_copy(update={
            "source_title": retrieved_by_id[citation.source_id]["title"],
            "source_type": retrieved_by_id[citation.source_id]["source_type"],
        })
        for citation in generated.citations
    ]

    return SupportResponse(
        classification=expected_classification,
        answer=generated.answer,
        sources=enriched_citations,
        confidence=generated.confidence,
        requires_human=(
            expected_classification == "requires_escalation"
        ),
        reason=(
            "The answer was generated from the retrieved local "
            "OrbitDesk evidence."
        ),
        reason_code=(
            "POLICY_REQUIRES_HUMAN"
            if expected_classification == "requires_escalation"
            else None
        ),
        clarification_question=None,
        warnings=[],
    )
