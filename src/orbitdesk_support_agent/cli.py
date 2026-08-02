import argparse
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local OrbitDesk support agent.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="OrbitDesk support question",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    question = " ".join(arguments.question).strip()

    if not question:
        question = input(
            "Enter an OrbitDesk support question: "
        ).strip()

    if not question:
        raise SystemExit("A support question is required.")

    documents = load_knowledge_base(
        PROJECT_ROOT / "knowledge_base"
    )
    cases = load_resolved_cases(
        PROJECT_ROOT / "resolved_cases.json"
    )
    records = build_evidence_records(documents, cases)

    print("Loading semantic retrieval model...")
    semantic_retriever = SemanticRetriever(records)

    print("Loading local language model...")
    llm = LocalLanguageModel()

    graph = build_graph(
        llm=llm,
        semantic_retriever=semantic_retriever,
    )

    execution_started = perf_counter()

    final_state = graph.invoke(
        {
            "question": question,
            "all_records": records,
            "retry_count": 0,
            "max_retries": 1,
            "execution_log": [],
            "verification_issues": [],
        }
    )

    execution_seconds = perf_counter() - execution_started
    response = final_state.get("response")

    if response is None:
        raise SystemExit(
            "The workflow finished without a response."
        )

    print("\nAnswer")
    print("------")
    print(response.answer)

    if response.clarification_question:
        print(response.clarification_question)

    print("\nStructured response")
    print("-------------------")
    print(response.model_dump_json(indent=2))

    print("\nExecution details")
    print("-----------------")
    print(
        "Nodes:",
        " -> ".join(final_state.get("execution_log", [])),
    )
    print(
        f"Retrieval mode: "
        f"{final_state.get('retrieval_mode', 'not used')}"
    )
    print(
        f"Embedding model load: "
        f"{semantic_retriever.model_load_seconds:.2f}s"
    )
    print(
        f"Embedding indexing: "
        f"{semantic_retriever.indexing_seconds:.2f}s"
    )
    print(f"LLM load: {llm.model_load_seconds:.2f}s")
    print(f"Workflow latency: {execution_seconds:.2f}s")

    if error := final_state.get("error"):
        print(f"Warning: {error}")


if __name__ == "__main__":
    main()