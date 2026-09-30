import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.evaluation import (
    evaluate_retriever,
    load_evaluation_cases,
)
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)
from orbitdesk_support_agent.retriever import retrieve_evidence


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SyntheticDataTests(unittest.TestCase):
    def test_checked_in_synthetic_data_loads_and_has_unique_ids(self):
        documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
        cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")
        records = build_evidence_records(documents, cases)
        source_ids = [record["source_id"] for record in records]

        self.assertGreaterEqual(len(documents), 5)
        self.assertGreaterEqual(len(cases), 12)
        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_retrieval_evaluation_data_references_known_sources(self):
        documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
        cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")
        records = build_evidence_records(documents, cases)
        known_ids = {record["source_id"] for record in records}
        evaluation_data = json.loads(
            (PROJECT_ROOT / "retrieval_eval.json").read_text(encoding="utf-8")
        )

        self.assertGreaterEqual(len(evaluation_data["cases"]), 14)
        for evaluation_case in evaluation_data["cases"]:
            self.assertTrue(
                set(evaluation_case["expected_source_ids"]) <= known_ids
            )

    def test_keyword_retrieval_meets_baseline_quality_floor(self):
        records = build_evidence_records(
            load_knowledge_base(PROJECT_ROOT / "knowledge_base"),
            load_resolved_cases(PROJECT_ROOT / "resolved_cases.json"),
        )
        evaluation_cases = load_evaluation_cases(
            PROJECT_ROOT / "retrieval_eval.json"
        )

        report = evaluate_retriever(
            records,
            evaluation_cases,
            lambda question, all_records, limit: retrieve_evidence(
                question,
                all_records,
                limit,
            ),
            limit=4,
        )

        self.assertGreaterEqual(report.hit_rate_at_k, 0.9)
        self.assertGreaterEqual(report.mean_reciprocal_rank, 0.7)

    def test_loader_rejects_unknown_document_status(self):
        with TemporaryDirectory() as directory:
            document = Path(directory) / "invalid.md"
            document.write_text(
                "---\n"
                "document_id: KB-BAD-001\n"
                "title: Invalid\n"
                "updated: 2026-09-26\n"
                "status: maybe\n"
                "tags: [invalid]\n"
                "---\n"
                "Invalid content.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "status"):
                load_knowledge_base(Path(directory))

    def test_loader_rejects_duplicate_case_ids(self):
        with TemporaryDirectory() as directory:
            case_file = Path(directory) / "cases.json"
            case = {
                "case_id": "CASE-DUP-001",
                "status": "current",
                "product_version": "synthetic-1",
                "title": "Duplicate",
                "symptoms": ["A symptom"],
                "resolution": ["A resolution"],
                "source_documents": ["KB-API-001"],
            }
            case_file.write_text(
                json.dumps({"cases": [case, case]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Duplicate case_id"):
                load_resolved_cases(case_file)


if __name__ == "__main__":
    unittest.main()
