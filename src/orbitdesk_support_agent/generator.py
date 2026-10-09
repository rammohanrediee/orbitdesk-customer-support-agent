import json
import re
from typing import Any, Protocol

from orbitdesk_support_agent.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from orbitdesk_support_agent.schemas import (
    Classification,
    EvidenceRecord,
    GeneratedAnswer,
    ReasonCode,
    SupportResponse,
)
from orbitdesk_support_agent.retriever import tokenize


class LanguageModel(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        ...


def _closest_exact_text(text: str, hint: str) -> str:
    normalized_text = " ".join(text.split())
    normalized_hint = " ".join(hint.split())
    if normalized_hint in normalized_text:
        return hint

    hint_tokens = tokenize(hint)
    candidates = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n+", text)
        if 0 < len(part.strip()) <= 500
    ]
    return max(
        candidates,
        key=lambda part: len(tokenize(part) & hint_tokens),
        default=hint,
    ) if any(tokenize(part) & hint_tokens for part in candidates) else hint


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
    expected_reason_code: ReasonCode | None = None,
    revision_feedback: list[str] | None = None,
    previous_response: SupportResponse | None = None,
) -> SupportResponse:
    if expected_reason_code == "INSUFFICIENT_EVIDENCE":
        return SupportResponse(
            classification="requires_escalation",
            answer=(
                "The available OrbitDesk documentation does not define these terms. "
                "A support specialist needs to confirm them."
            ),
            sources=[],
            confidence=0.0,
            requires_human=True,
            reason="The supplied documentation is insufficient.",
            reason_code=expected_reason_code,
        )

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
            f"only these issues and preserve the other fields: {feedback}"
        )
        if previous_response is not None:
            user_prompt += (
                "\nPrevious attempt:\n"
                f"{previous_response.model_dump_json()}"
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

    enriched_citations = []
    for citation in generated.citations:
        record = retrieved_by_id[citation.source_id]
        passage = _closest_exact_text(record["text"], citation.passage)
        claim = (
            _closest_exact_text(generated.answer, citation.claim)
            if citation.claim
            else None
        )
        enriched_citations.append(citation.model_copy(update={
            "passage": passage,
            "claim": claim,
            "source_title": record["title"],
            "source_type": record["source_type"],
        }))

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
            expected_reason_code
            or (
                "POLICY_REQUIRES_HUMAN"
                if expected_classification == "requires_escalation"
                else None
            )
        ),
        clarification_question=None,
        warnings=[],
    )
