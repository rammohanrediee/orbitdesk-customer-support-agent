import numpy as np

from orbitdesk_support_agent.semantic_retriever import SemanticRetriever


class FakeEmbeddingModel:
    def __init__(self):
        self.calls = 0

    def encode(self, texts, **_kwargs):
        self.calls += 1
        return np.asarray([
            [1.0, 0.0] if "credential" in text.lower() else [0.0, 1.0]
            for text in texts
        ])


def test_semantic_retriever_indexes_once_and_ranks_current_records() -> None:
    model = FakeEmbeddingModel()
    retriever = SemanticRetriever(
        [
            {"source_id": "KB-1", "source_type": "knowledge_base", "title": "Credentials", "text": "Credential policy", "status": "current"},
            {"source_id": "KB-2", "source_type": "knowledge_base", "title": "Exports", "text": "Export schedule", "status": "current"},
            {"source_id": "OLD", "source_type": "resolved_case", "title": "Old", "text": "Credential legacy", "status": "superseded"},
        ],
        model=model,
    )

    assert retriever.retrieve("credential access", limit=1)[0]["source_id"] == "KB-1"
    assert model.calls == 2
    assert {record["source_id"] for record in retriever.records} == {"KB-1", "KB-2"}
