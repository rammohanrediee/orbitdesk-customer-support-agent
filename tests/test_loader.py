from pathlib import Path

import pytest

from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_PATH = PROJECT_ROOT / "knowledge_base"
RESOLVED_CASES_PATH = PROJECT_ROOT / "resolved_cases.json"


def test_load_knowledge_base() -> None:
    documents = load_knowledge_base(KNOWLEDGE_BASE_PATH)

    assert len(documents) == 10
    assert documents[0]["document_id"] == "KB-001"

    for document in documents:
        assert document["document_id"]
        assert document["content"]
        assert document["source_file"]


def test_load_resolved_cases() -> None:
    cases = load_resolved_cases(RESOLVED_CASES_PATH)

    assert len(cases) == 12
    assert cases[0]["case_id"] == "CASE-1041"
    assert sum(case["status"] == "superseded" for case in cases) == 1


def test_missing_knowledge_base_raises_file_not_found(
    tmp_path: Path,
) -> None:
    missing_directory = tmp_path / "missing-knowledge-base"

    with pytest.raises(FileNotFoundError):
        load_knowledge_base(missing_directory)


def test_missing_resolved_cases_raises_file_not_found(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing-cases.json"

    with pytest.raises(FileNotFoundError):
        load_resolved_cases(missing_file)


def test_resolved_cases_requires_cases_list(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid-cases.json"
    invalid_file.write_text('{"cases": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a 'cases' list"):
        load_resolved_cases(invalid_file)
