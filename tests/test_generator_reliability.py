import json
import unittest

from orbitdesk_support_agent.generator import generate_response
from orbitdesk_support_agent.schemas import SupportResponse
from orbitdesk_support_agent.verifier import verify_response


EVIDENCE = [
    {
        "source_id": "KB-API-001",
        "source_type": "knowledge_base",
        "title": "API credentials",
        "text": "Only workspace owners can rotate API credentials.",
        "status": "current",
    }
]


class FakeLanguageModel:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, system_prompt, user_prompt):
        return json.dumps(self.payload)


class ReliableGenerationTests(unittest.TestCase):
    def test_uses_model_supplied_exact_citation(self):
        model = FakeLanguageModel(
            {
                "answer": "Ask a workspace owner to rotate the credential.",
                "citations": [
                    {
                        "source_id": "KB-API-001",
                        "passage": (
                            "Only workspace owners can rotate API credentials."
                        ),
                    }
                ],
                "confidence": 0.91,
            }
        )

        response = generate_response(
            "Who rotates credentials?",
            EVIDENCE,
            model,
        )

        self.assertEqual(response.sources[0].source_id, "KB-API-001")
        self.assertEqual(response.confidence, 0.91)
        self.assertTrue(verify_response(response, EVIDENCE).passed)

    def test_rejects_citation_for_unretrieved_source(self):
        model = FakeLanguageModel(
            {
                "answer": "Unsupported.",
                "citations": [
                    {
                        "source_id": "KB-NOT-RETRIEVED",
                        "passage": "Invented evidence.",
                    }
                ],
                "confidence": 0.8,
            }
        )

        with self.assertRaisesRegex(ValueError, "not retrieved"):
            generate_response("question", EVIDENCE, model)

    def test_verifier_rejects_non_exact_passage(self):
        response = SupportResponse(
            classification="answerable",
            answer="An unsupported answer.",
            sources=[
                {
                    "source_id": "KB-API-001",
                    "passage": "Administrators can rotate credentials.",
                }
            ],
            confidence=0.8,
            requires_human=False,
            reason="Generated from evidence.",
        )

        result = verify_response(response, EVIDENCE)

        self.assertFalse(result.passed)
        self.assertIn("exact excerpt", result.issues[0])


if __name__ == "__main__":
    unittest.main()

