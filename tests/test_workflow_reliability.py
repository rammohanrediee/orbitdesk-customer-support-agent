import unittest

from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.nodes import MAX_WORKFLOW_RETRIES
from orbitdesk_support_agent.trace import request_trace


EVIDENCE = [
    {
        "source_id": "KB-API-001",
        "source_type": "knowledge_base",
        "title": "API credentials",
        "text": "Only workspace owners can create API credentials.",
        "status": "current",
    }
]


class StaticRetriever:
    def retrieve(self, question, limit):
        return EVIDENCE[:limit]


class InvalidGenerationModel:
    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return "not-json"


class RaisingModel:
    def generate(self, system_prompt, user_prompt):
        raise TimeoutError("provider timed out with internal details")


class StructuredAnswerModel:
    def generate(self, system_prompt, user_prompt):
        return (
            '{"answer":"Ask a workspace owner.",'
            '"citations":[{"source_id":"KB-API-001",'
            '"passage":"Only workspace owners can create API credentials."}],'
            '"confidence":0.9}'
        )


def initial_state(question, max_retries=99):
    return {
        "question": question,
        "all_records": EVIDENCE,
        "retry_count": 0,
        "max_retries": max_retries,
        "execution_log": [],
        "verification_issues": [],
    }


class WorkflowReliabilityTests(unittest.TestCase):
    def test_successful_answer_records_completion_events(self):
        graph = build_graph(StructuredAnswerModel(), StaticRetriever())

        with request_trace("trace-success") as trace:
            final_state = graph.invoke(
                initial_state("Can I create an API credential?")
            )

        self.assertEqual(final_state["response"].classification, "answerable")
        self.assertTrue(final_state["verification_passed"])
        event_names = [event.name for event in trace.events]
        self.assertIn("workflow.retrieval.completed", event_names)
        self.assertIn("workflow.verification.completed", event_names)

    def test_deterministic_clarification_does_not_call_model(self):
        graph = build_graph(RaisingModel(), StaticRetriever())

        final_state = graph.invoke(initial_state("OrbitDesk is not working"))

        self.assertEqual(
            final_state["response"].classification,
            "requires_clarification",
        )

    def test_deterministic_out_of_scope_does_not_call_model(self):
        graph = build_graph(RaisingModel(), StaticRetriever())

        final_state = graph.invoke(initial_state("Please issue a refund"))

        self.assertEqual(final_state["response"].classification, "out_of_scope")

    def test_workflow_clamps_generation_retries(self):
        model = InvalidGenerationModel()
        graph = build_graph(model, StaticRetriever())

        with request_trace("trace-retries") as trace:
            final_state = graph.invoke(
                initial_state("Can I create an API credential?")
            )

        self.assertEqual(
            model.calls,
            MAX_WORKFLOW_RETRIES + 1,
        )
        self.assertEqual(final_state["response"].classification, "safe_failure")
        event_names = [event.name for event in trace.events]
        self.assertIn("workflow.generation.failed", event_names)
        self.assertIn("workflow.safe_failure", event_names)

    def test_triage_provider_failure_becomes_safe_failure(self):
        graph = build_graph(RaisingModel(), StaticRetriever())

        with request_trace("trace-triage") as trace:
            final_state = graph.invoke(
                initial_state("Please diagnose an unusual workspace problem")
            )

        self.assertEqual(final_state["response"].classification, "safe_failure")
        self.assertNotIn("internal details", final_state["response"].answer)
        self.assertIn(
            "workflow.triage.failed",
            [event.name for event in trace.events],
        )


if __name__ == "__main__":
    unittest.main()
