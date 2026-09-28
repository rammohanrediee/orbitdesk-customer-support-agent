import unittest

from orbitdesk_support_agent.retriever import KeywordRetriever


class KeywordRetrieverTests(unittest.TestCase):
    def test_exposes_graph_compatible_retrieve_method(self):
        records = [
            {
                "source_id": "KB-TIME-001",
                "source_type": "knowledge_base",
                "title": "Export timezone",
                "text": "Scheduled exports use the workspace timezone.",
                "status": "current",
            }
        ]
        retriever = KeywordRetriever(records)

        results = retriever.retrieve("workspace export timezone", limit=1)

        self.assertEqual(results[0]["source_id"], "KB-TIME-001")


if __name__ == "__main__":
    unittest.main()
