# OrbitDesk Local Support Agent

OrbitDesk is a local-first support agent for a fictional workspace product. It
loads the supplied product documentation and resolved cases, retrieves relevant
evidence, generates a structured answer with a local Hugging Face model, and
verifies that the response is grounded in the retrieved sources.

## Project status

This repository is a work in progress. The data loading, evidence indexing,
keyword and semantic retrieval, local model wrapper, triage, generation,
verification, retry state, and core node functions are implemented. The final
LangGraph assembly, conditional triage routes, safe-failure node, CLI, graph
diagram, end-to-end tests, and sample run outputs are still being completed.

## Planned workflow

```text
question -> triage -> retrieve -> generate -> verify
                |                         |
                |                         +-> retry -> generate
                +-> clarification / escalation / out of scope
```

Semantic retrieval is attempted first. If it fails, the retrieval node falls
back to deterministic keyword ranking. Superseded cases are excluded, and
current knowledge-base documents take priority over resolved cases.

## Local models

- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
  - Revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- Generation: `Qwen/Qwen2.5-1.5B-Instruct`
  - Revision: `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`

The runtime selects Apple MPS first, then NVIDIA CUDA, and otherwise uses the
CPU. Network access is needed for the initial model download only.

## Setup

Python 3.12 is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The package currently uses a `src` layout without packaging metadata, so set
`PYTHONPATH` when running tests:

```bash
PYTHONPATH=src pytest -q
```

Current result: `12 passed`.

## Repository contents

- `knowledge_base/`: current OrbitDesk product documentation
- `resolved_cases.json`: historical support cases
- `sample_questions.json`: five supplied workflow questions
- `output_schema.json`: structured response schema
- `src/orbitdesk_support_agent/`: agent implementation
- `tests/`: loader, indexer, and keyword-retrieval tests

Knowledge-base documents are the primary source of truth. Resolved cases are
secondary evidence, and cases marked `superseded` must never be presented as
current guidance.

## AI assistance disclosure

An AI coding assistant was used while developing this assignment for guided
explanations, implementation review, debugging, and documentation. The design
choices and submitted implementation were reviewed incrementally by the
candidate.
