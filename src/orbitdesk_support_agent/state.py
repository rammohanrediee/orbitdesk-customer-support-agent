import operator
from typing import Annotated, TypedDict

from orbitdesk_support_agent.schemas import (
    EvidenceRecord,
    RetrievalMode,
    SupportResponse,TriageResult)


class AgentState(TypedDict, total=False):
    question: str
    all_records: list[EvidenceRecord]
    retrieved_evidence: list[EvidenceRecord]
    response: SupportResponse | None
    verification_passed: bool
    verification_issues: list[str]
    retry_count: int
    max_retries: int
    execution_log: Annotated[list[str], operator.add]
    retrieval_mode: RetrievalMode
    error: str | None
    triage_result: TriageResult | None
