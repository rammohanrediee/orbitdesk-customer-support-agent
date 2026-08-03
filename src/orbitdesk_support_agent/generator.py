import json
from typing import Any, Protocol

from orbitdesk_support_agent.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from orbitdesk_support_agent.schemas import (
    Classification,
    EvidenceRecord,
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
            classification="safe_failure",
            answer=(
                "I could not find relevant information in the supplied "
                "OrbitDesk knowledge base."
            ),
            sources=[],
            confidence=0.0,
            requires_human=False,
            reason="No relevant evidence was retrieved.",
            clarification_question=None,
            warnings=["The local model was not called."],
        )

    user_prompt = build_user_prompt(question, records)
    user_prompt = (
        f"{user_prompt}\n\n"
        f"The workflow classification is {expected_classification}.\n"
        "Return only the readable answer, without JSON, headings, "
        "or a preamble. Keep the answer under 100 words. Give only "
        "instructions supported by the supplied evidence."
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
    answer = raw_response.strip()

    if not answer:
        raise ValueError("The model returned an empty answer.")

    sources = [
        {
            "source_id": record["source_id"],
            "passage": " ".join(record["text"].split())[:240],
        }
        for record in records[:3]
    ]

    return SupportResponse(
        classification=expected_classification,
        answer=answer,
        sources=sources,
        confidence=0.8,
        requires_human=(
            expected_classification == "requires_escalation"
        ),
        reason=(
            "The answer was generated from the retrieved local "
            "OrbitDesk evidence."
        ),
        clarification_question=None,
        warnings=[],
    )
