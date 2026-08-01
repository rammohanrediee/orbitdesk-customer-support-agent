from pathlib import Path

from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)
from orbitdesk_support_agent.retriever import retrieve_evidence, tokenize
from orbitdesk_support_agent.schemas import EvidenceRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_records() -> list[EvidenceRecord]:
    documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
    cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")
    return build_evidence_records(documents, cases)


def test_tokenize_normalizes_words_and_removes_stop_words() -> None:
    assert tokenize("What is the API credential?") == {"api", "credential"}


def test_retrieve_evidence_finds_api_credential_sources() -> None:
    results = retrieve_evidence(
        "Can a Viewer create an API credential?",
        _load_records(),
    )
    source_ids = {record["source_id"] for record in results}

    assert "KB-005" in source_ids
    assert "CASE-0914" not in source_ids
    assert len(results) <= 4


def test_retrieve_evidence_excludes_superseded_records() -> None:
    results = retrieve_evidence(
        "legacy personal token",
        _load_records(),
        limit=20,
    )

    assert all(record["status"] != "superseded" for record in results)


def test_retrieve_evidence_prefers_knowledge_base_on_tie() -> None:
    case: EvidenceRecord = {
        "source_id": "CASE-1",
        "source_type": "resolved_case",
        "title": "API credential",
        "text": "API credential",
        "status": "resolved",
    }
    document: EvidenceRecord = {
        "source_id": "KB-1",
        "source_type": "knowledge_base",
        "title": "API credential",
        "text": "API credential",
        "status": "current",
    }

    results = retrieve_evidence("API credential", [case, document])

    assert [record["source_id"] for record in results] == ["KB-1", "CASE-1"]


def test_retrieve_evidence_handles_empty_query_and_nonpositive_limit() -> None:
    records = _load_records()

    assert retrieve_evidence("the and is", records) == []
    assert retrieve_evidence("credential", records, limit=0) == []
