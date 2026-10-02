from orbitdesk_support_agent.generator import generate_response
from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.schemas import SourceReference, SupportResponse
from orbitdesk_support_agent.verifier import verify_response


class UnusedModel:
    def generate(self, system_prompt, user_prompt):
        raise AssertionError("No model call is needed without evidence")


class EmptyRetriever:
    retrieval_mode = "keyword"

    def retrieve(self, question, limit):
        return []


def test_missing_evidence_escalates_with_structured_reason():
    graph = build_graph(UnusedModel(), EmptyRetriever())
    result = graph.invoke({
        "question": "Can a Viewer create an API credential?",
        "all_records": [],
        "retry_count": 0,
        "max_retries": 1,
        "execution_log": [],
        "verification_issues": [],
    })

    response = result["response"]
    assert response.classification == "requires_escalation"
    assert response.reason_code == "INSUFFICIENT_EVIDENCE"
    assert response.requires_human is True
    assert response.sources == []
    assert result["verification_passed"] is True


def test_citation_claim_must_match_the_answer():
    response = SupportResponse(
        classification="answerable",
        answer="Owners can create credentials.",
        sources=[SourceReference(
            source_id="KB-005",
            passage="Owners can create credentials.",
            claim="Viewers can create credentials.",
        )],
        confidence=0.5,
        requires_human=False,
        reason="Supported by KB.",
    )
    evidence = [{
        "source_id": "KB-005",
        "title": "API credentials",
        "source_type": "knowledge_base",
        "text": "Owners can create credentials.",
        "status": "current",
    }]

    result = verify_response(response, evidence)
    assert result.passed is False
    assert any("claim" in issue for issue in result.issues)


def test_provider_failure_has_model_failure_reason_code():
    class FailingModel:
        def generate(self, system_prompt, user_prompt):
            raise TimeoutError("provider timed out")

    graph = build_graph(FailingModel(), EmptyRetriever())
    result = graph.invoke({
        "question": "Please diagnose an unusual workspace problem",
        "all_records": [],
        "retry_count": 0,
        "max_retries": 1,
        "execution_log": [],
        "verification_issues": [],
    })
    assert result["response"].classification == "safe_failure"
    assert result["response"].reason_code == "MODEL_FAILURE"
