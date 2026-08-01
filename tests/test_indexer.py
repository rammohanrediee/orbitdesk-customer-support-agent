from pathlib import Path

from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_evidence_records_combines_all_sources() -> None:
    documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
    cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")

    records = build_evidence_records(documents, cases)

    assert len(records) == 18
    assert sum(
        record["source_type"] == "knowledge_base" for record in records
    ) == 10
    assert sum(
        record["source_type"] == "resolved_case" for record in records
    ) == 8


def test_build_evidence_records_preserves_source_information() -> None:
    documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
    cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")

    records = build_evidence_records(documents, cases)
    records_by_id = {record["source_id"]: record for record in records}

    assert records_by_id["KB-001"]["status"] == "current"
    assert "OrbitDesk Product Overview" in records_by_id["KB-001"]["text"]
    assert records_by_id["CASE-0914"]["status"] == "superseded"
    assert "Superseded reason:" in records_by_id["CASE-0914"]["text"]
