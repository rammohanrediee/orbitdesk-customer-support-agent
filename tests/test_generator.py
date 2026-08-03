from orbitdesk_support_agent.generator import generate_response
from orbitdesk_support_agent.schemas import EvidenceRecord


class RecordingLLM:
    def __init__(self) -> None:
        self.user_prompt = ""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        self.user_prompt = user_prompt
        return "Only Admins can create credentials."


def test_generation_wraps_readable_answer_in_valid_schema() -> None:
    llm = RecordingLLM()
    records: list[EvidenceRecord] = [
        {
            "source_id": "KB-005",
            "source_type": "knowledge_base",
            "title": "API credentials",
            "text": "Admins can create credentials.",
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
    assert "Keep the answer under 100 words" in llm.user_prompt
    assert "Return only the readable answer" in llm.user_prompt
    assert "required_output_schema" not in llm.user_prompt


def test_escalation_response_requires_a_human() -> None:
    llm = RecordingLLM()
    records: list[EvidenceRecord] = [
        {
            "source_id": "KB-008",
            "source_type": "knowledge_base",
            "title": "Escalations",
            "text": "Escalate after two documented failures.",
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


def test_generation_records_at_most_three_retrieved_sources() -> None:
    llm = RecordingLLM()
    records: list[EvidenceRecord] = [
        {
            "source_id": f"KB-00{index}",
            "source_type": "knowledge_base",
            "title": f"Document {index}",
            "text": f"Supporting evidence {index}.",
            "status": "current",
        }
        for index in range(1, 5)
    ]

    response = generate_response(
        question="What should I check?",
        records=records,
        llm=llm,
    )

    assert [source.source_id for source in response.sources] == [
        "KB-001",
        "KB-002",
        "KB-003",
    ]
