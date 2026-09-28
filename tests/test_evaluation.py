import unittest

from orbitdesk_support_agent.evaluation import (
    EvaluationCase,
    evaluate_retriever,
)


RECORDS = [
    {
        "source_id": "KB-API-001",
        "source_type": "knowledge_base",
        "title": "API credential permissions",
        "text": "Only workspace owners can create or rotate API credentials.",
        "status": "current",
    },
    {
        "source_id": "KB-TIME-001",
        "source_type": "knowledge_base",
        "title": "Scheduled export timezone",
        "text": "Scheduled exports use the workspace timezone.",
        "status": "current",
    },
    {
        "source_id": "KB-CONN-001",
        "source_type": "knowledge_base",
        "title": "Connector retry guidance",
        "text": "Reconnect after checking OAuth scopes and the connector status.",
        "status": "current",
    },
]


class RetrievalEvaluationTests(unittest.TestCase):
    def test_computes_hit_rate_and_mean_reciprocal_rank(self):
        cases = [
            EvaluationCase(
                case_id="E-1",
                question="Who can rotate API credentials?",
                expected_source_ids=("KB-API-001",),
            ),
            EvaluationCase(
                case_id="E-2",
                question="Which timezone is used for scheduled exports?",
                expected_source_ids=("KB-TIME-001",),
            ),
        ]

        def retrieve(question, records, limit):
            if "credential" in question:
                return [records[0], records[1]][:limit]
            return [records[2], records[1]][:limit]

        report = evaluate_retriever(RECORDS, cases, retrieve, limit=2)

        self.assertEqual(report.case_count, 2)
        self.assertEqual(report.hit_rate_at_k, 1.0)
        self.assertEqual(report.mean_reciprocal_rank, 0.75)

    def test_reports_a_miss_without_dividing_by_zero(self):
        case = EvaluationCase(
            case_id="E-1",
            question="Unknown",
            expected_source_ids=("KB-API-001",),
        )

        report = evaluate_retriever(
            RECORDS,
            [case],
            lambda question, records, limit: [],
            limit=3,
        )

        self.assertEqual(report.hit_rate_at_k, 0.0)
        self.assertEqual(report.mean_reciprocal_rank, 0.0)
        self.assertFalse(report.results[0].hit)

    def test_rejects_invalid_evaluation_configuration(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            evaluate_retriever(RECORDS, [], lambda *_: [], limit=1)

        case = EvaluationCase("E-1", "question", ("KB-API-001",))
        with self.assertRaisesRegex(ValueError, "positive"):
            evaluate_retriever(RECORDS, [case], lambda *_: [], limit=0)


if __name__ == "__main__":
    unittest.main()
