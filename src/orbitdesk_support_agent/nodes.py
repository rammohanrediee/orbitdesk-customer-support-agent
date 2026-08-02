from collections.abc import Callable
from typing import Literal, Protocol

from orbitdesk_support_agent.generator import (
    LanguageModel,
    generate_response,
)
from orbitdesk_support_agent.model_config import MAX_RETRIEVED_RECORDS
from orbitdesk_support_agent.retriever import retrieve_evidence
from orbitdesk_support_agent.schemas import (
    EvidenceRecord,
    SupportResponse,
)
from orbitdesk_support_agent.state import AgentState
from orbitdesk_support_agent.triage import triage_question
from orbitdesk_support_agent.verifier import verify_response

TriageRoute = Literal[
    "retrieve",
    "clarification",
    "out_of_scope",
    "safe_failure",
]


class SemanticRetrieverProtocol(Protocol):
    def retrieve(
        self,
        question: str,
        limit: int,
    ) -> list[EvidenceRecord]:
        ...


VerificationRoute = Literal[
    "complete",
    "retry",
    "safe_failure",
]


def route_after_verification(
    state: AgentState,
) -> VerificationRoute:
    if state.get("verification_passed", False):
        return "complete"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if retry_count < max_retries:
        return "retry"

    return "safe_failure"


def create_retry_node() -> Callable[[AgentState], AgentState]:
    def retry_node(state: AgentState) -> AgentState:
        retry_count = state.get("retry_count", 0)

        return {
            "retry_count": retry_count + 1,
            "response": None,
            "verification_passed": False,
            "verification_issues": [],
            "execution_log": ["retry"],
        }

    return retry_node


def create_triage_node(
    llm: LanguageModel,
) -> Callable[[AgentState], AgentState]:
    def triage_node(state: AgentState) -> AgentState:
        question = state.get("question", "")

        result = triage_question(
            question=question,
            llm=llm,
        )

        return {
            "triage_result": result,
            "execution_log": ["triage"],
        }

    return triage_node


def create_retrieval_node(
    semantic_retriever: SemanticRetrieverProtocol,
) -> Callable[[AgentState], AgentState]:
    def retrieval_node(state: AgentState) -> AgentState:
        question = state.get("question", "")
        all_records = state.get("all_records", [])

        try:
            retrieved = semantic_retriever.retrieve(
                question,
                limit=MAX_RETRIEVED_RECORDS,
            )

            return {
                "retrieved_evidence": retrieved,
                "retrieval_mode": "semantic",
                "execution_log": ["retrieve:semantic"],
                "error": None,
            }

        except Exception as error:
            retrieved = retrieve_evidence(
                question=question,
                records=all_records,
                limit=MAX_RETRIEVED_RECORDS,
            )

            return {
                "retrieved_evidence": retrieved,
                "retrieval_mode": "keyword",
                "execution_log": [
                    "retrieve:keyword_fallback"
                ],
                "error": (
                    "Semantic retrieval failed: "
                    f"{type(error).__name__}: {error}"
                ),
            }

    return retrieval_node


def create_generation_node(
    llm: LanguageModel,
) -> Callable[[AgentState], AgentState]:
    def generation_node(state: AgentState) -> AgentState:
        question = state.get("question", "")
        evidence = state.get("retrieved_evidence", [])

        response = generate_response(
            question=question,
            records=evidence,
            llm=llm,
        )

        return {
            "response": response,
            "execution_log": ["generate"],
        }

    return generation_node


def create_verification_node() -> Callable[[AgentState], AgentState]:
    def verification_node(state: AgentState) -> AgentState:
        response = state.get("response")
        evidence = state.get("retrieved_evidence", [])

        if response is None:
            return {
                "verification_passed": False,
                "verification_issues": [
                    "No generated response was available."
                ],
                "execution_log": ["verify:failed"],
            }

        result = verify_response(
            response=response,
            evidence=evidence,
        )

        log_entry = (
            "verify:passed"
            if result.passed
            else "verify:failed"
        )

        return {
            "verification_passed": result.passed,
            "verification_issues": result.issues,
            "execution_log": [log_entry],
        }

    return verification_node


def create_safe_failure_node() -> Callable[[AgentState], AgentState]:
    def safe_failure_node(state: AgentState) -> AgentState:
        issues = state.get("verification_issues", [])

        response = SupportResponse(
            classification="safe_failure",
            answer=(
                "I could not produce a reliable answer from the "
                "available OrbitDesk documentation."
            ),
            sources=[],
            confidence=0.0,
            requires_human=False,
            reason=(
                "The generated response did not pass verification "
                "after the allowed retries."
            ),
            clarification_question=None,
            warnings=issues,
        )

        return {
            "response": response,
            "verification_passed": False,
            "execution_log": ["safe_failure"],
        }

    return safe_failure_node


def route_after_triage(
    state: AgentState,
) -> TriageRoute:
    triage_result = state.get("triage_result")

    if triage_result is None:
        return "safe_failure"

    classification = triage_result.classification

    if classification in {
        "answerable",
        "requires_escalation",
    }:
        return "retrieve"

    if classification == "requires_clarification":
        return "clarification"

    if classification == "out_of_scope":
        return "out_of_scope"

    return "safe_failure"


def create_clarification_node() -> Callable[[AgentState], AgentState]:
    def clarification_node(state: AgentState) -> AgentState:
        triage_result = state.get("triage_result")

        clarification_question = (
            triage_result.clarification_question
            if triage_result is not None
            else None
        )

        if not clarification_question:
            clarification_question = (
                "Could you provide more details about the "
                "OrbitDesk issue?"
            )

        reason = (
            triage_result.reason
            if triage_result is not None
            else "More information is required."
        )

        response = SupportResponse(
            classification="requires_clarification",
            answer=(
                "I need some additional information before I can "
                "provide reliable guidance."
            ),
            sources=[],
            confidence=0.0,
            requires_human=False,
            reason=reason,
            clarification_question=clarification_question,
            warnings=[],
        )

        return {
            "response": response,
            "execution_log": ["clarification"],
        }

    return clarification_node


def create_out_of_scope_node() -> Callable[[AgentState], AgentState]:
    def out_of_scope_node(state: AgentState) -> AgentState:
        triage_result = state.get("triage_result")

        reason = (
            triage_result.reason
            if triage_result is not None
            else "The request is outside OrbitDesk support."
        )

        response = SupportResponse(
            classification="out_of_scope",
            answer=(
                "I can only help with questions supported by the "
                "provided OrbitDesk documentation."
            ),
            sources=[],
            confidence=1.0,
            requires_human=False,
            reason=reason,
            clarification_question=None,
            warnings=[],
        )

        return {
            "response": response,
            "execution_log": ["out_of_scope"],
        }

    return out_of_scope_node
