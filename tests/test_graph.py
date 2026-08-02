import json

from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.schemas import EvidenceRecord


class ClarificationLLM:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        if "triage component" not in system_prompt:
            raise AssertionError(
                "Generation should not run for clarification."
            )

        return json.dumps(
            {
                "classification": "requires_clarification",
                "reason": "The connection type is missing.",
                "clarification_question": (
                    "Which type of data connection is failing?"
                ),
            }
        )


class UnusedRetriever:
    def __init__(self) -> None:
        self.called = False

    def retrieve(
        self,
        question: str,
        limit: int,
    ) -> list[EvidenceRecord]:
        self.called = True
        return []


def test_clarification_route_skips_retrieval() -> None:
    retriever = UnusedRetriever()

    graph = build_graph(
        llm=ClarificationLLM(),
        semantic_retriever=retriever,
    )

    result = graph.invoke(
        {
            "question": "Our data sync is not working.",
            "all_records": [],
            "retry_count": 0,
            "max_retries": 1,
            "execution_log": [],
            "verification_issues": [],
        }
    )

    assert result["response"].classification == (
        "requires_clarification"
    )
    assert result["execution_log"] == [
        "triage",
        "clarification",
    ]
    assert retriever.called is False


class RetryThenPassLLM:
    def __init__(self) -> None:
        self.generation_calls = 0

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        if "triage component" in system_prompt:
            return json.dumps(
                {
                    "classification": "answerable",
                    "reason": "The question concerns API credentials.",
                    "clarification_question": None,
                }
            )

        self.generation_calls += 1

        if self.generation_calls == 1:
            # Structurally valid but verification must reject it
            # because an answerable response has no sources.
            return json.dumps(
                {
                    "classification": "answerable",
                    "answer": "A Viewer cannot create credentials.",
                    "sources": [],
                    "confidence": 0.5,
                    "requires_human": False,
                    "reason": "The role does not have permission.",
                    "clarification_question": None,
                    "warnings": [],
                }
            )

        return json.dumps(
            {
                "classification": "answerable",
                "answer": (
                    "A Viewer cannot create API credentials."
                ),
                "sources": [
                    {
                        "source_id": "KB-005",
                        "passage": (
                            "Only Owners and Admins can create "
                            "API credentials."
                        ),
                    }
                ],
                "confidence": 0.9,
                "requires_human": False,
                "reason": "Supported by the permissions documentation.",
                "clarification_question": None,
                "warnings": [],
            }
        )


class FixedRetriever:
    def retrieve(
        self,
        question: str,
        limit: int,
    ) -> list[EvidenceRecord]:
        return [
            {
                "source_id": "KB-005",
                "source_type": "knowledge_base",
                "title": "API Credentials",
                "text": (
                    "Only Owners and Admins can create "
                    "API credentials."
                ),
                "status": "current",
            }
        ]


def test_failed_verification_retries_once() -> None:
    llm = RetryThenPassLLM()

    graph = build_graph(
        llm=llm,
        semantic_retriever=FixedRetriever(),
    )

    result = graph.invoke(
        {
            "question": (
                "Can a Viewer create an API credential?"
            ),
            "all_records": [],
            "retry_count": 0,
            "max_retries": 1,
            "execution_log": [],
            "verification_issues": [],
        }
    )

    assert result["verification_passed"] is True
    assert result["retry_count"] == 1
    assert llm.generation_calls == 2
    assert result["execution_log"] == [
        "triage",
        "retrieve:semantic",
        "generate",
        "verify:failed",
        "retry",
        "generate",
        "verify:passed",
    ]
