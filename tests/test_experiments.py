import json
from pathlib import Path

import pytest

from orbitdesk_support_agent.experiments import compare_reports, generate_live_outputs, run_experiment


def test_experiment_records_dataset_identity_and_partial_coverage(tmp_path: Path):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"cases": [
        {"question_id": "Q-1", "question": "Can Owners manage billing?", "expected_classification": "answerable", "expected_requires_human": False, "required_source_ids": ["KB-1"], "required_answer_terms": ["Owners"]},
        {"question_id": "Q-2", "question": "Unknown policy?", "expected_classification": "requires_escalation", "expected_requires_human": True, "required_source_ids": [], "required_answer_terms": []},
    ]}), encoding="utf-8")
    outputs = tmp_path / "outputs.json"
    outputs.write_text("[]", encoding="utf-8")
    records = [{"source_id": "KB-1", "title": "Billing", "text": "Owners manage billing.", "source_type": "knowledge_base", "status": "current"}]

    report = run_experiment("keyword-test", labels, outputs, records, "keyword", 1)

    assert report["dataset"]["case_count"] == 2
    assert len(report["dataset"]["sha256"]) == 64
    assert report["retrieval"]["case_count"] == 1
    assert report["retrieval"]["hit_rate_at_k"] == 1.0
    assert report["answers"]["evaluated_count"] == 0
    assert report["answers"]["missing_count"] == 2
    assert report["config"]["top_k"] == 1


def test_report_identifies_live_outputs_without_regenerating_them(tmp_path: Path):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"cases": [
        {"question_id": "Q-1", "question": "Owners?", "expected_classification": "answerable", "expected_requires_human": False, "required_source_ids": ["KB-1"], "required_answer_terms": []},
    ]}), encoding="utf-8")
    outputs = tmp_path / "outputs.json"
    outputs.write_text("[]", encoding="utf-8")
    records = [{"source_id": "KB-1", "title": "Owners", "text": "Owners.", "source_type": "knowledge_base", "status": "current"}]
    report = run_experiment("live-test", labels, outputs, records, "keyword", 4, outputs_kind="live")
    assert report["saved_outputs"]["kind"] == "live"


def test_comparison_rejects_mismatched_datasets():
    left = {"experiment": "one", "dataset": {"sha256": "a"}, "retrieval": {}, "answers": {}}
    right = {"experiment": "two", "dataset": {"sha256": "b"}, "retrieval": {}, "answers": {}}
    with pytest.raises(ValueError, match="same dataset"):
        compare_reports([left, right])


def test_experiment_rejects_unknown_expected_source(tmp_path: Path):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"cases": [
        {"question_id": "Q-1", "question": "Question", "expected_classification": "answerable", "expected_requires_human": False, "required_source_ids": ["MISSING"], "required_answer_terms": []}
    ]}), encoding="utf-8")
    outputs = tmp_path / "outputs.json"
    outputs.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown source"):
        run_experiment("bad", labels, outputs, [], "keyword", 3)


def test_live_generation_needs_provider_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        generate_live_outputs([], Path("unused.json"))
