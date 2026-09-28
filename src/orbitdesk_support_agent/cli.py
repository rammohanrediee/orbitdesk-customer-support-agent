import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)
from orbitdesk_support_agent.nodes import MAX_WORKFLOW_RETRIES
from orbitdesk_support_agent.openrouter_llm import OpenRouterLanguageModel
from orbitdesk_support_agent.retriever import KeywordRetriever
from orbitdesk_support_agent.trace import record_trace_event, request_trace


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = (
    PACKAGE_ROOT.parents[1]
    if PACKAGE_ROOT.parent.name == "src"
    else PACKAGE_ROOT
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local OrbitDesk support agent.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="OrbitDesk support question",
    )
    parser.add_argument(
        "--retrieval",
        choices=("keyword", "semantic"),
        default=os.getenv("ORBITDESK_RETRIEVAL_MODE", "keyword"),
        help="Retrieval backend; semantic requires the optional semantic extra.",
    )
    parser.add_argument(
        "--workflow-timeout-seconds",
        type=float,
        default=float(os.getenv("ORBITDESK_WORKFLOW_TIMEOUT_SECONDS", "60")),
        help="End-to-end deadline shared by all model calls.",
    )
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print redacted structured trace events.",
    )

    return parser.parse_args()


def build_retriever(records, mode: str):
    if mode == "keyword":
        return KeywordRetriever(records)

    try:
        from orbitdesk_support_agent.semantic_retriever import (
            SemanticRetriever,
        )
    except ImportError as error:
        raise SystemExit(
            "Semantic retrieval requires: pip install -e '.[semantic]'"
        ) from error
    return SemanticRetriever(records)


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

    if arguments.workflow_timeout_seconds <= 0:
        raise SystemExit("Workflow timeout must be positive.")

    print(f"Loading {arguments.retrieval} retrieval...")
    retriever = build_retriever(records, arguments.retrieval)

    print("Configuring OpenRouter language model...")
    try:
        llm = OpenRouterLanguageModel()
    except ValueError as error:
        raise SystemExit(str(error)) from error

    graph = build_graph(
        llm=llm,
        semantic_retriever=retriever,
    )

    execution_started = perf_counter()

    with request_trace(
        timeout_seconds=arguments.workflow_timeout_seconds,
    ) as trace:
        record_trace_event(
            "request.started",
            question_chars=len(question),
            retrieval_mode=arguments.retrieval,
        )
        final_state = graph.invoke(
            {
                "question": question,
                "all_records": records,
                "retry_count": 0,
                "max_retries": MAX_WORKFLOW_RETRIES,
                "execution_log": [],
                "verification_issues": [],
            }
        )
        response = final_state.get("response")
        record_trace_event(
            "request.completed",
            classification=(
                response.classification if response is not None else "missing"
            ),
            retry_count=final_state.get("retry_count", 0),
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
    print(f"Model: {llm.config.model}")
    print(f"Trace ID: {trace.trace_id}")
    print(f"Workflow latency: {execution_seconds:.2f}s")

    if error := final_state.get("error"):
        print(f"Warning: {error}")

    if arguments.show_trace:
        print("\nRequest trace")
        print("-------------")
        print(json.dumps(trace.to_dict(), indent=2))


if __name__ == "__main__":
    main()
