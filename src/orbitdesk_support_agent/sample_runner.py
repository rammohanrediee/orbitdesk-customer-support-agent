import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

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
        description=(
            "Generate sample output safely. Prefer one question per "
            "process on memory-constrained computers."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--question-id",
        help="Generate or replace one sample, for example Q-001",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Generate all samples in one process (uses more memory)",
    )

    return parser.parse_args()


def select_samples(
    samples: list[dict[str, str]],
    question_id: str | None,
) -> list[dict[str, str]]:
    if question_id is None:
        return samples

    selected = [
        sample
        for sample in samples
        if sample["question_id"] == question_id
    ]

    if not selected:
        raise ValueError(f"Unknown question ID: {question_id}")

    return selected


def merge_output(
    existing: list[dict[str, Any]],
    replacement: dict[str, Any],
) -> list[dict[str, Any]]:
    merged = list(existing)

    for index, output in enumerate(merged):
        if output["question_id"] == replacement["question_id"]:
            merged[index] = replacement
            return merged

    merged.append(replacement)
    return merged


def main() -> None:
    arguments = parse_arguments()
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

    selected_samples = select_samples(
        sample_data["questions"],
        arguments.question_id,
    )
    output_path = PROJECT_ROOT / "sample_outputs.json"

    if arguments.question_id and output_path.exists():
        outputs = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        outputs = []

    for sample in selected_samples:
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

        output = {
            "question_id": sample["question_id"],
            "question": sample["question"],
            "response": response.model_dump(),
            "execution_log": state["execution_log"],
            "retrieval_mode": state.get("retrieval_mode"),
            "latency_seconds": round(
                perf_counter() - started,
                2,
            ),
            "runtime": {
                "device": llm.device,
                "embedding_model_load_seconds": round(
                    retriever.model_load_seconds,
                    2,
                ),
                "embedding_indexing_seconds": round(
                    retriever.indexing_seconds,
                    2,
                ),
                "llm_load_seconds": round(
                    llm.model_load_seconds,
                    2,
                ),
            },
        }

        outputs = merge_output(outputs, output)

    output_path.write_text(
        json.dumps(outputs, indent=2),
        encoding="utf-8",
    )

    print(
        f"Saved {len(selected_samples)} generated output(s); "
        f"{len(outputs)} total in {output_path}"
    )


if __name__ == "__main__":
    main()
