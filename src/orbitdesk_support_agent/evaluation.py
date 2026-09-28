"""Deterministic retrieval evaluation for OrbitDesk datasets."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Callable, Sequence


Record = dict[str, Any]
Retriever = Callable[[str, list[Record], int], list[Record]]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("Evaluation case ID must not be empty.")
        if not self.question.strip():
            raise ValueError("Evaluation question must not be empty.")
        if not self.expected_source_ids:
            raise ValueError("Evaluation case needs an expected source ID.")


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    expected_source_ids: tuple[str, ...]
    retrieved_source_ids: tuple[str, ...]
    hit: bool
    reciprocal_rank: float


@dataclass(frozen=True)
class EvaluationReport:
    limit: int
    case_count: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float
    results: tuple[EvaluationResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "case_count": self.case_count,
            "hit_rate_at_k": self.hit_rate_at_k,
            "mean_reciprocal_rank": self.mean_reciprocal_rank,
            "results": [asdict(result) for result in self.results],
        }


def evaluate_retriever(
    records: list[Record],
    cases: Sequence[EvaluationCase],
    retrieve: Retriever,
    *,
    limit: int,
) -> EvaluationReport:
    if not cases:
        raise ValueError("Evaluation requires at least one case.")
    if limit <= 0:
        raise ValueError("Evaluation retrieval limit must be positive.")

    results: list[EvaluationResult] = []
    for case in cases:
        retrieved = retrieve(case.question, records, limit)
        source_ids = tuple(str(record["source_id"]) for record in retrieved)
        expected = set(case.expected_source_ids)
        first_relevant_rank = next(
            (
                rank
                for rank, source_id in enumerate(source_ids, start=1)
                if source_id in expected
            ),
            None,
        )
        reciprocal_rank = (
            0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
        )
        results.append(
            EvaluationResult(
                case_id=case.case_id,
                expected_source_ids=case.expected_source_ids,
                retrieved_source_ids=source_ids,
                hit=first_relevant_rank is not None,
                reciprocal_rank=reciprocal_rank,
            )
        )

    hit_rate = sum(result.hit for result in results) / len(results)
    mean_reciprocal_rank = sum(
        result.reciprocal_rank for result in results
    ) / len(results)

    return EvaluationReport(
        limit=limit,
        case_count=len(results),
        hit_rate_at_k=round(hit_rate, 4),
        mean_reciprocal_rank=round(mean_reciprocal_rank, 4),
        results=tuple(results),
    )


def load_evaluation_cases(file_path: Path) -> list[EvaluationCase]:
    data = json.loads(file_path.read_text(encoding="utf-8"))
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Evaluation data must contain a non-empty cases list.")

    cases: list[EvaluationCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("Every evaluation case must be an object.")
        expected = raw_case.get("expected_source_ids")
        if not isinstance(expected, list) or not all(
            isinstance(source_id, str) for source_id in expected
        ):
            raise ValueError("expected_source_ids must be a list of strings.")
        cases.append(
            EvaluationCase(
                case_id=str(raw_case.get("case_id", "")),
                question=str(raw_case.get("question", "")),
                expected_source_ids=tuple(expected),
            )
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate OrbitDesk keyword retrieval against labelled data."
    )
    parser.add_argument("--limit", type=int, default=4)
    arguments = parser.parse_args()

    from orbitdesk_support_agent.indexer import build_evidence_records
    from orbitdesk_support_agent.loader import (
        load_knowledge_base,
        load_resolved_cases,
    )
    from orbitdesk_support_agent.retriever import retrieve_evidence

    package_root = Path(__file__).resolve().parent
    project_root = (
        package_root.parents[1]
        if package_root.parent.name == "src"
        else package_root
    )
    records = build_evidence_records(
        load_knowledge_base(project_root / "knowledge_base"),
        load_resolved_cases(project_root / "resolved_cases.json"),
    )
    cases = load_evaluation_cases(project_root / "retrieval_eval.json")

    report = evaluate_retriever(
        records,
        cases,
        lambda question, all_records, limit: retrieve_evidence(
            question,
            all_records,
            limit,
        ),
        limit=arguments.limit,
    )
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
