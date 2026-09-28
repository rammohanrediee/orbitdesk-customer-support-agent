import { Braces, Copy, FileSearch, Gauge, Workflow } from "lucide-react";
import { useState } from "react";

export default function Inspector({ result }) {
  const [tab, setTab] = useState("request");
  const [copied, setCopied] = useState(false);
  const traceId = result?.trace?.trace_id;
  const events = result?.trace?.events ?? [];

  async function copyTraceId() {
    if (!traceId) return;
    try {
      await navigator.clipboard.writeText(traceId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <aside className="inspector" aria-label="Request inspector">
      <div className="inspector__header">
        <div>
          <p>Inspector</p>
          <h2>Request detail</h2>
        </div>
        <Braces aria-hidden="true" size={18} />
      </div>

      <div className="inspector__tabs" role="tablist" aria-label="Inspector view">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "request"}
          onClick={() => setTab("request")}
        >
          Request
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "trace"}
          onClick={() => setTab("trace")}
        >
          Trace
        </button>
      </div>

      {tab === "request" ? (
        <div className="inspector__panel" role="tabpanel">
          <dl className="request-spec">
            <div>
              <dt><Workflow aria-hidden="true" size={14} /> Route</dt>
              <dd>{result?.execution_log?.join(" → ") ?? "Waiting for a request"}</dd>
            </div>
            <div>
              <dt><FileSearch aria-hidden="true" size={14} /> Retrieval</dt>
              <dd>{result?.retrieval_mode ?? "—"}</dd>
            </div>
            <div>
              <dt><Gauge aria-hidden="true" size={14} /> Latency</dt>
              <dd className="tnum">
                {result ? `${result.latency_seconds.toFixed(2)} s` : "—"}
              </dd>
            </div>
          </dl>
          <div className="inspector__model">
            <span>Model</span>
            <code>{result?.model ?? "z-ai/glm-4.5-air"}</code>
          </div>
        </div>
      ) : (
        <div className="inspector__panel" role="tabpanel">
          <div className="trace-id">
            <div>
              <span>Trace ID</span>
              <code>{traceId ?? "Not available"}</code>
            </div>
            <button
              type="button"
              className="copy-button"
              onClick={copyTraceId}
              disabled={!traceId}
              data-state={copied ? "success" : "default"}
            >
              <Copy aria-hidden="true" size={15} />
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
          <ol className="trace-events">
            {events.length ? (
              events.map((event, index) => (
                <li key={`${event.name}-${index}`}>
                  <span className="trace-events__dot" aria-hidden="true" />
                  <div>
                    <code>{event.name}</code>
                    <span className="tnum">{event.elapsed_ms.toFixed(1)} ms</span>
                  </div>
                </li>
              ))
            ) : (
              <li className="trace-events__empty">
                Run a question to inspect redacted trace events.
              </li>
            )}
          </ol>
        </div>
      )}
    </aside>
  );
}
