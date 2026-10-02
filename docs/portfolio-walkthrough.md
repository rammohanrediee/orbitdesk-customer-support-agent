# OrbitDesk portfolio walkthrough

OrbitDesk is a fictional support product. The corpus, incidents, questions, and five recorded answers are synthetic. The agent drafts a decision for a human reviewer; it does not send customer messages or execute refunds, credential changes, or other external actions.

## Three-minute demo

1. Set `ORBITDESK_POSTGRES_PASSWORD` and `ORBITDESK_OPERATOR_TOKEN`, run `docker compose up --build`, and open `http://127.0.0.1:8000`. Enter the operator token at the access gate.
2. Ask the recorded timezone/export question. Inspect the answer and open a full cited source from the evidence panel.
3. Ask the repeated `render_failed` question. Show the structured escalation reason and safe details for handoff.
4. Approve, edit, or escalate a ticket. Refresh and reopen it to demonstrate persistent decision and review history.
5. Show `evaluation_results/keyword-k4.json` beside `keyword-k4-v2.json` and `live-keyword-v2.json`: retrieval improved on Q-008, while the live answer score exposes real limitations.

## Architecture and design choices

```text
React → FastAPI → LangGraph triage → retrieval → OpenRouter draft
                                         → citation verification → retry/safe failure
              ↘ PostgreSQL: Ticket → Decision → Citation
                                      ↘ Review
```

The backend keeps one structured decision per ticket and a separate review action. It stores key fields in relational columns and only uses JSON for bounded trace/log/warning structures. The reviewer can see source title, type, exact passage, and full source text. The API keeps credentials server-side. The default keyword retriever is cheap and deterministic; optional semantic retrieval needs local model dependencies. Resolved cases are secondary evidence, and superseded cases are excluded.

## Evaluation interpretation

The fixed dataset has 30 cases. Twenty-three have labeled source IDs for retrieval metrics; seven are intentionally source-free. The initial keyword scorer hit 22/23 sources at K=4; the revised coverage-aware scorer hit 23/23. The five recorded demo answers passed 5/5 behavior checks. A separate live OpenRouter run evaluated all 30 final responses: 12/30 passed all checks; answer correctness was 7/19; escalation precision was 2/3 and recall 2/6. Eleven questions safely failed verification rather than receiving unsupported answers. The exact-passage groundedness check is a proxy; it cannot prove every generated claim is entailed by its citations.

Q-008 was the visible retrieval miss at K=4. It asks when a Viewer may download an export; the initial scorer favored export/destination records over the role-permissions document. The v2 scorer rewards coverage of the whole query and now retrieves the role policy. The live run still has substantial generation and verification failures; retrieval improvement alone is not answer-quality improvement.

## Reliability and deployment boundary

Provider requests and graph retries are bounded. Invalid citations and provider failure lead to safe failure or explicit escalation, never a fabricated answer. A shared operator token can protect ticket, source, model, and review API calls; the browser holds it only in memory. Production requires this gate and a retention policy, but this is not per-user identity or authorization. The retention command previews by default and only deletes old reviewed tickets with `--apply`; pending tickets stay. A public deployment still needs HTTPS, rate limiting, privacy review, and ideally individual user accounts. Use synthetic data only. Docker Compose includes PostgreSQL but could not be run end-to-end in the current environment because the Docker daemon was unavailable; configuration validation and application tests were run.
