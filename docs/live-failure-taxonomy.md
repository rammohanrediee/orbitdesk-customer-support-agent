# Live failure taxonomy

Baseline: `evaluation_results/live-keyword-v2.json` and
`evaluation_results/live-keyword-v2-outputs.json`, generated on 2026-10-01 with
`z-ai/glm-4.5-air`, keyword retrieval at K=4, and the 30-case
`answer_eval.json` dataset.

The baseline passed 12 of 30 cases. All 18 failures are accounted for below.

## Implemented corrections

- Generation now canonicalizes paraphrased citation passages and claims to exact source and answer text before verification.
- Known retention, credential-recovery, pricing and contract boundaries route deterministically; unsupported commercial terms use `INSUFFICIENT_EVIDENCE`.
- Evaluation accepts `save`/`resave` wording and treats a resolved case as evidence for its declared source documents.
- Retry feedback uses stable issue codes and includes the previous response.

With evaluator-only corrections, the unchanged v2 outputs rescore from 12/30 to 15/30. This is not a new live run and does not measure the generation and routing changes above.

| Category | Cases | Count | What failed |
| --- | --- | ---: | --- |
| Verification rejected usable generation | Q-002, Q-004, Q-007, Q-009, Q-010, Q-011, Q-012, Q-018, Q-022, Q-028, Q-030 | 11 | Claim text was not copied into the answer exactly, a citation passage was not an exact retrieved excerpt, or both. The bounded retry then returned `safe_failure`. |
| Triage chose the wrong route | Q-015, Q-019, Q-025, Q-026 | 4 | A documented question was clarified, a documented refusal was escalated, or an unsupported commercial/contract question was answered or clarified instead of escalated for insufficient evidence. |
| Evaluator required a specific secondary source | Q-020, Q-021 | 2 | The answer and action were correct, but the generated response used a relevant resolved case instead of the required `KB-008` citation. |
| Lexical evaluation false negative | Q-001 | 1 | The answer said "save it" and correctly included "Run now"; the label required the exact token "resave". |

## Case-level disposition

| Case | Primary cause | Next change |
| --- | --- | --- |
| Q-001 | Required-term matcher is too literal. | Accept `save`/`resave` variants or use phrase groups. |
| Q-002 | Claim linkage and exact-excerpt verification failed. | Constrain generation to copy evidence excerpts and answer claims verbatim. |
| Q-004 | Exact-excerpt verification failed across escalation evidence. | Keep escalation wording, but force citations to be selected substrings. |
| Q-007 | Claim text did not appear exactly in the answer. | Make claim generation quote the answer span exactly. |
| Q-009 | Claim text did not appear exactly in the answer. | Make claim generation quote the answer span exactly. |
| Q-010 | Claim text did not appear exactly in the answer. | Make claim generation quote the answer span exactly. |
| Q-011 | Citation passage was not an exact retrieved excerpt. | Validate and repair citation passages before final verification. |
| Q-012 | Resolved-case citation passage was not exact. | Validate and repair citation passages before final verification. |
| Q-015 | Triage requested details already supplied by the question. | Route documented retention questions to retrieval. |
| Q-018 | Claim text did not appear exactly in the answer. | Make claim generation quote the answer span exactly. |
| Q-019 | Safe documented refusal was treated as human-required. | Reserve escalation for actions or policy-defined human review. |
| Q-020 | Correct answer used `CASE-1144` instead of required `KB-008`. | Allow equivalent evidence or require the authoritative KB source consistently. |
| Q-021 | Correct answer used `CASE-1152` instead of required `KB-008`. | Allow equivalent evidence or require the authoritative KB source consistently. |
| Q-022 | Resolved-case citation passage was not exact. | Validate and repair citation passages before final verification. |
| Q-025 | Missing pricing/refund evidence was presented as an answer. | Escalate unsupported commercial questions with `INSUFFICIENT_EVIDENCE`. |
| Q-026 | Missing contract evidence was treated as clarification. | Escalate account-specific contract questions with `INSUFFICIENT_EVIDENCE`. |
| Q-028 | Claim text did not appear exactly in the answer. | Make claim generation quote the answer span exactly and prefer current KB evidence. |
| Q-030 | Citation passage was not an exact retrieved excerpt. | Validate and repair citation passages before final verification. |

## Rerun contract

A second live generation must use the same dataset hash, retrieval mode, K,
model, and output cap. It must create a new outputs file; rescoring the existing
outputs is not a second run.

```bash
OPENROUTER_API_KEY='...' .venv/bin/orbitdesk-experiment \
  --experiment live-keyword-v3 \
  --retrieval keyword \
  --top-k 4 \
  --live

.venv/bin/orbitdesk-experiment --compare \
  evaluation_results/live-keyword-v2.json \
  evaluation_results/live-keyword-v3.json
```

The v3 report should publish the full 30-case result, not only improved cases.
The run is pending because no `OPENROUTER_API_KEY` is available in the current
environment.
