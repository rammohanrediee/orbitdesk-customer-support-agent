"""Reproducible retrieval and saved-answer experiments on one fixed dataset."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from orbitdesk_support_agent.answer_evaluation import AnswerCase, evaluate_answers, load_answer_cases
from orbitdesk_support_agent.evaluation import EvaluationCase, evaluate_retriever
from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import load_knowledge_base, load_resolved_cases
from orbitdesk_support_agent.model_config import EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_REVISION, MAX_RETRIEVED_RECORDS
from orbitdesk_support_agent.retriever import retrieve_evidence
from orbitdesk_support_agent.schemas import EvidenceRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_dirty() -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def generate_live_outputs(cases: list[AnswerCase], destination: Path) -> None:
    """Explicitly run every label through the current OpenRouter workflow."""
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise ValueError("OPENROUTER_API_KEY is required for --live.")
    if os.getenv("ORBITDESK_DEMO_MODE", "").strip() == "1":
        raise ValueError("Disable ORBITDESK_DEMO_MODE for --live.")
    from orbitdesk_support_agent.api import SupportRequest, run_support_workflow

    destination.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []
    for case in cases:
        try:
            result = run_support_workflow(SupportRequest(question=case.question))
            output = {
                "question_id": case.question_id,
                "question": case.question,
                "response": result.response,
                "execution_log": result.execution_log,
                "retrieval_mode": result.retrieval_mode,
                "model": result.model,
                "prompt_version": "v1",
                "latency_seconds": result.latency_seconds,
            }
        except Exception as error:
            output = {
                "question_id": case.question_id,
                "question": case.question,
                "error_type": type(error).__name__,
            }
        outputs.append(output)
        destination.write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")


def run_experiment(
    name: str,
    labels_path: Path,
    outputs_path: Path,
    records: list[EvidenceRecord],
    retrieval_mode: str,
    top_k: int,
    outputs_kind: str = "recorded",
) -> dict[str, Any]:
    if not name or not all(char.isalnum() or char in "-_" for char in name):
        raise ValueError("Experiment name must contain only letters, numbers, - or _.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    if outputs_kind not in {"recorded", "live"}:
        raise ValueError("outputs_kind must be recorded or live.")
    cases = load_answer_cases(labels_path)
    known_sources = {record["source_id"] for record in records}
    unknown = sorted({source_id for case in cases for source_id in case.required_source_ids} - known_sources)
    if unknown:
        raise ValueError(f"Evaluation labels contain unknown source IDs: {', '.join(unknown)}")
    outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    if not isinstance(outputs, list):
        raise ValueError("Saved outputs must be a JSON list.")
    unknown_outputs = {output["question_id"] for output in outputs} - {case.question_id for case in cases}
    if unknown_outputs:
        raise ValueError(f"Saved outputs contain unknown case IDs: {', '.join(sorted(unknown_outputs))}")

    retrieval_cases = [
        EvaluationCase(case.question_id, case.question, case.required_source_ids)
        for case in cases if case.required_source_ids
    ]
    if retrieval_mode == "keyword":
        retrieve = retrieve_evidence
        embedding_model = None
    elif retrieval_mode == "semantic":
        from orbitdesk_support_agent.semantic_retriever import SemanticRetriever

        semantic = SemanticRetriever(records)

        def retrieve(question, _records, limit):
            return semantic.retrieve(question, limit)

        embedding_model = f"{EMBEDDING_MODEL_NAME}@{EMBEDDING_MODEL_REVISION}"
    else:
        raise ValueError("retrieval_mode must be keyword or semantic.")

    retrieval = evaluate_retriever(records, retrieval_cases, retrieve, limit=top_k).to_dict()
    answers = evaluate_answers(cases, outputs, records)
    model_names = sorted({output.get("model", "unknown (legacy recording)") for output in outputs})
    return {
        "experiment": name,
        "run_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "dataset": {
            "path": _display_path(labels_path),
            "sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
            "case_count": len(cases),
        },
        "saved_outputs": {
            "path": _display_path(outputs_path),
            "sha256": hashlib.sha256(outputs_path.read_bytes()).hexdigest(),
            "count": len(outputs),
            "model_names": model_names,
            "kind": outputs_kind,
            "note": (
                "These outputs were generated by the live workflow using this retrieval configuration."
                if outputs_kind == "live"
                else "Recorded outputs are evaluated as saved; retrieval configuration does not regenerate them."
            ),
        },
        "config": {
            "retrieval_strategy": retrieval_mode,
            "embedding_model": embedding_model,
            "top_k": top_k,
            "prompt_version": sorted({output.get("prompt_version", "unknown (legacy recordings)") for output in outputs}),
            "pipeline_version": "v1",
        },
        "retrieval": retrieval,
        "answers": answers,
    }


def compare_reports(reports: list[dict[str, Any]]) -> str:
    if len(reports) < 2:
        raise ValueError("Compare at least two experiment reports.")
    hashes = {report["dataset"]["sha256"] for report in reports}
    if len(hashes) != 1:
        raise ValueError("Experiments must use the same dataset for comparison.")
    header = "Experiment | Retrieval | Hit@K | MRR | Answers checked | Answer correct | Grounded proxy | Escalation recall"
    divider = "--- | --- | ---: | ---: | ---: | ---: | ---: | ---:"

    def shown(value: Any) -> str:
        return "n/a" if value is None else f"{value:.2%}"

    rows = [header, divider]
    for report in reports:
        retrieval = report["retrieval"]
        answers = report["answers"]
        rows.append(" | ".join([
            report["experiment"],
            f"{report['config']['retrieval_strategy']}@{report['config']['top_k']}",
            shown(retrieval["hit_rate_at_k"]),
            f"{retrieval['mean_reciprocal_rank']:.3f}",
            f"{answers['evaluated_count']}/{answers['case_count']}",
            shown(answers["answer_correctness"]),
            shown(answers["grounded_response_rate"]),
            shown(answers["escalation_recall"]),
        ]))
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or compare OrbitDesk quality experiments.")
    parser.add_argument("--experiment", help="Version name for a new run")
    parser.add_argument("--retrieval", choices=["keyword", "semantic"], default="keyword")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--labels", type=Path, default=PROJECT_ROOT / "answer_eval.json")
    parser.add_argument("--outputs", type=Path, default=PROJECT_ROOT / "sample_outputs.json")
    parser.add_argument("--outputs-kind", choices=["recorded", "live"], default="recorded")
    parser.add_argument("--results-dir", type=Path, default=PROJECT_ROOT / "evaluation_results")
    parser.add_argument("--compare", nargs="+", type=Path, help="Compare saved JSON reports")
    parser.add_argument("--live", action="store_true", help="Generate all label outputs through OpenRouter (uses provider credits)")
    args = parser.parse_args()

    if args.compare:
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.compare]
        print(compare_reports(reports))
        return
    if not args.experiment:
        parser.error("--experiment is required for a new run")

    if args.live:
        if args.top_k != MAX_RETRIEVED_RECORDS:
            parser.error(f"--live uses the workflow's fixed top_k={MAX_RETRIEVED_RECORDS}")
        os.environ["ORBITDESK_RETRIEVAL_MODE"] = args.retrieval
        args.outputs = args.results_dir / f"{args.experiment}-outputs.json"
        generate_live_outputs(load_answer_cases(args.labels), args.outputs)
        args.outputs_kind = "live"

    records = build_evidence_records(
        load_knowledge_base(PROJECT_ROOT / "knowledge_base"),
        load_resolved_cases(PROJECT_ROOT / "resolved_cases.json"),
    )
    report = run_experiment(args.experiment, args.labels, args.outputs, records, args.retrieval, args.top_k, args.outputs_kind)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.results_dir / f"{args.experiment}.json"
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {output_path}")
    print(f"Retrieval: {report['retrieval']['case_count']} labeled cases; Hit@{args.top_k}={report['retrieval']['hit_rate_at_k']:.1%}, MRR={report['retrieval']['mean_reciprocal_rank']:.3f}")
    print(f"Answers: {report['answers']['evaluated_count']}/{report['answers']['case_count']} cases with saved outputs; {report['answers']['missing_count']} not run")
    if args.outputs_kind == "recorded":
        print("Answer metrics describe saved recordings, not a fresh generation with this retrieval setting.")


if __name__ == "__main__":
    main()
