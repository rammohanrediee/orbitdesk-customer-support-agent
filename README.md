# OrbitDesk Customer Support Agent

OrbitDesk is a retrieval-grounded support workflow backed by OpenRouter. It
loads a synthetic product knowledge base and resolved-case corpus, retrieves
relevant evidence, produces a structured answer, and rejects citations that
are not exact excerpts from the retrieved sources.

## Tech stack

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-GLM_4.5_Air-6467F2?style=for-the-badge)](https://openrouter.ai/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflow-1C3C3C?style=for-the-badge)](https://www.langchain.com/langgraph)
[![Pydantic](https://img.shields.io/badge/Pydantic-Typed_Schemas-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Sentence Transformers](https://img.shields.io/badge/Sentence_Transformers-Optional_Semantic_Retrieval-2E7D32?style=for-the-badge)](https://www.sbert.net/)
[![PyTorch](https://img.shields.io/badge/PyTorch-Optional_ML_Runtime-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Hugging Face](https://img.shields.io/badge/Hugging_Face-Optional_Local_Runtime-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/docs/transformers/)
[![pytest](https://img.shields.io/badge/pytest-63_Passing-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Coverage](https://img.shields.io/badge/Coverage-83%25-2E7D32?style=for-the-badge)](https://coverage.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-6DAE30?style=for-the-badge)](LICENSE)

- OpenRouter with `z-ai/glm-4.5-air` handles generation and model-assisted
  triage through a bounded standard-library HTTP client.
- LangGraph coordinates triage, retrieval, generation, verification, retry,
  and safe-failure routes.
- Pydantic validates model output and the final support-response schema.
- Dependency-light keyword retrieval is the default; Sentence Transformers
  remains available for optional local semantic retrieval.
- PyTorch and the Hugging Face ecosystem remain optional ML dependencies;
  the default keyword/OpenRouter path does not require them.

![OrbitDesk agent graph](docs/orbitdesk-agent-graph.png)

## Model choice

OpenRouter does not currently list a Z.ai model named GLM 3.5. The default is
`z-ai/glm-4.5-air`, the closest likely intended model for a low-latency support
workflow. Set `OPENROUTER_MODEL` to use another OpenRouter model without a code
change.

The former `LocalLanguageModel` import remains as a compatibility alias, but
the CLI and sample runner now use the bounded OpenRouter client.

## Setup

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Export the API key in the shell before running the CLI. The application does
not automatically read `.env`, so secrets are not loaded implicitly.

```bash
export OPENROUTER_API_KEY='your-key'
orbitdesk-support --show-trace \
  'Who can create an OrbitDesk API credential?'
```

Keyword retrieval is the dependency-light default. Local semantic retrieval
is available as an optional extra:

```bash
python -m pip install -e '.[semantic]'
orbitdesk-support --retrieval semantic 'your question'
```

## Evaluation and tests

`retrieval_eval.json` is a labeled synthetic evaluation set for the checked-in
OrbitDesk corpus. It reports HitRate@K, mean reciprocal rank, and per-query
rankings.

```bash
orbitdesk-evaluate --limit 4
python -m pytest -q
coverage run -m pytest
coverage report
```

The current keyword baseline scores HitRate@4 `1.0` and MRR `0.9` across ten
queries. Coverage is configured to fail below 80% for the core modules.

## Reliability boundaries

- OpenRouter attempts: maximum 3 by default, hard maximum 5.
- Workflow generation retries: maximum 1.
- Per-attempt network timeout: 20 seconds by default.
- OpenRouter call deadline: 45 seconds by default.
- End-to-end CLI deadline: 60 seconds by default.
- LLM input: 16,000 characters; output: 256 tokens by default.
- Response body: maximum 1 MiB.
- Trace events never store questions, prompts, authorization headers, or keys.
- Generated citations must name retrieved sources and quote exact evidence.

All configurable limits are documented in `.env.example`.

## Repository contents

- `src/orbitdesk_support_agent/`: workflow, retrieval, model client, tracing,
  and evaluation code
- `knowledge_base/`: synthetic OrbitDesk product documentation
- `resolved_cases.json`: synthetic historical support cases
- `retrieval_eval.json`: labeled synthetic retrieval benchmark
- `sample_questions.json`: example workflow questions
- `tests/`: unit, workflow, retry, timeout, trace, and evaluation tests
- `docs/`: workflow diagram assets

Knowledge-base documents are the primary source of truth. Resolved cases are
secondary evidence, and superseded cases are never returned as current
guidance.

## License

This project is licensed under the [MIT License](LICENSE).
