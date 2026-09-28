import json

from orbitdesk_support_agent.generator import generate_response
from orbitdesk_support_agent.schemas import EvidenceRecord


class RecordingLLM:
    def __init__(self, source_id: str, passage: str) -> None:
        self.source_id = source_id
        self.passage = passage
        self.user_prompt = ""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return json.dumps(
            {
                "answer": "Only Admins can create credentials.",
                "citations": [
                    {
                        "source_id": self.source_id,
                        "passage": self.passage,
                    }
                ],
                "confidence": 0.9,
            }
        )


def test_generation_requires_structured_grounded_output() -> None:
    passage = "Admins can create credentials."
    llm = RecordingLLM("KB-005", passage)
    records: list[EvidenceRecord] = [
        {
            "source_id": "KB-005",
            "source_type": "knowledge_base",
            "title": "API credentials",
            "text": passage,
            "status": "current",
        }
    ]

    response = generate_response(
        question="Can a Viewer create a credential?",
        records=records,
        llm=llm,
    )

    assert response.classification == "answerable"
    assert response.answer == "Only Admins can create credentials."
    assert response.sources[0].source_id == "KB-005"
    assert response.sources[0].passage == passage
    assert "Return only one JSON object" in llm.user_prompt
    assert "copied exactly" in llm.user_prompt


def test_escalation_response_requires_a_human() -> None:
    passage = "Escalate after two documented failures."
    llm = RecordingLLM("KB-008", passage)
    records: list[EvidenceRecord] = [
        {
            "source_id": "KB-008",
            "source_type": "knowledge_base",
            "title": "Escalations",
            "text": passage,
            "status": "current",
        }
    ]

    response = generate_response(
        question="Two runs failed. What next?",
        records=records,
        llm=llm,
        expected_classification="requires_escalation",
    )

    assert response.classification == "requires_escalation"
    assert response.requires_human is True
