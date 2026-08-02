import json
from pathlib import Path
from time import perf_counter

from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)
from orbitdesk_support_agent.local_llm import LocalLanguageModel
from orbitdesk_support_agent.semantic_retriever import SemanticRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    sample_data = json.loads(
        (PROJECT_ROOT / "sample_questions.json").read_text(
            encoding="utf-8"
        )
    )

    documents = load_knowledge_base(
        PROJECT_ROOT / "knowledge_base"
    )
    cases = load_resolved_cases(
        PROJECT_ROOT / "resolved_cases.json"
    )
    records = build_evidence_records(documents, cases)

    retriever = SemanticRetriever(records)
    llm = LocalLanguageModel()
    graph = build_graph(llm, retriever)

    outputs = []

    for sample in sample_data["questions"]:
        started = perf_counter()

        state = graph.invoke(
            {
                "question": sample["question"],
                "all_records": records,
                "retry_count": 0,
                "max_retries": 1,
                "execution_log": [],
                "verification_issues": [],
            }
        )

        response = state["response"]

        outputs.append(
            {
                "question_id": sample["question_id"],
                "question": sample["question"],
                "response": response.model_dump(),
                "execution_log": state["execution_log"],
                "retrieval_mode": state.get("retrieval_mode"),
                "latency_seconds": round(
                    perf_counter() - started,
                    2,
                ),
            }
        )

    output_path = PROJECT_ROOT / "sample_outputs.json"
    output_path.write_text(
        json.dumps(outputs, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {len(outputs)} outputs to {output_path}")


if __name__ == "__main__":
    main()