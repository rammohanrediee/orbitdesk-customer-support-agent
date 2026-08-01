import json
from typing import Any, Protocol

from orbitdesk_support_agent.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from orbitdesk_support_agent.schemas import (
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
    output_schema = json.dumps(
        SupportResponse.model_json_schema(),
        indent=2,
    )

    user_prompt = (
        f"{user_prompt}\n\n"
        "<required_output_schema>\n"
        f"{output_schema}\n"
        "</required_output_schema>\n\n"
        "Return only one valid JSON object matching this schema."
    )

    raw_response = llm.generate(
        SYSTEM_PROMPT,
        user_prompt,
    )

    parsed_response = extract_json_object(raw_response)
    response = SupportResponse.model_validate(parsed_response)

    allowed_source_ids = {
        record["source_id"]
        for record in records
    }
    generated_source_ids = {
        source.source_id
        for source in response.sources
    }

    invented_source_ids = (
        generated_source_ids - allowed_source_ids
    )

    if invented_source_ids:
        raise ValueError(
            "The generated response cited unavailable sources: "
            f"{sorted(invented_source_ids)}"
        )

    return response