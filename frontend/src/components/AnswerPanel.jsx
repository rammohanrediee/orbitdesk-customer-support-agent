import {
  BookMarked,
  CircleAlert,
  ShieldCheck,
} from "lucide-react";
import EvidenceSource from "./EvidenceSource.jsx";
import ReviewPanel from "./ReviewPanel.jsx";

function classificationLabel(classification) {
  return classification?.replaceAll("_", " ") ?? "waiting";
}

const reasonLabels = {
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  INSUFFICIENT_INFORMATION: "More information needed",
  CONFLICTING_SOURCES: "Conflicting sources",
  OUT_OF_SCOPE: "Outside support scope",
  VERIFICATION_FAILED: "Source verification failed",
  MODEL_FAILURE: "Model unavailable",
  POLICY_REQUIRES_HUMAN: "Policy requires a person",
};

export default function AnswerPanel({ result, ticket, status, error, reviewError, reviewBusy, onReview }) {
  if (status === "error") {
    return (
      <section className="answer-panel answer-panel--error" aria-live="polite">
        <CircleAlert aria-hidden="true" size={24} />
        <div>
          <h2>The request did not complete</h2>
          <p>{error}</p>
          <p className="answer-panel__secondary">
            Check the API server and OpenRouter configuration, then try again.
          </p>
        </div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="answer-empty" aria-labelledby="answer-empty-title">
        <div className="answer-empty__mark" aria-hidden="true">
          <BookMarked size={30} />
        </div>
        <div>
          <h2 id="answer-empty-title">No answer yet</h2>
          <p>
            Ask a product question. OrbitDesk retrieves local evidence,
            generates a bounded response, and verifies every citation.
          </p>
        </div>
      </section>
    );
  }

  const response = result.response;
  return (
    <section className="answer-panel" aria-live="polite">
      <header className="answer-panel__header">
        <div className="answer-panel__classification">
          <ShieldCheck aria-hidden="true" size={18} />
          <span>{classificationLabel(response.classification)}</span>
        </div>
      </header>

      <div className="answer-panel__body">
        <h2>Support draft</h2>
        <p className="answer-panel__answer">{response.answer}</p>
        {response.clarification_question && (
          <p className="answer-panel__clarification">
            {response.clarification_question}
          </p>
        )}
        {response.requires_human && (
          <p className="answer-panel__escalation">
            Human review required: {response.reason}
          </p>
        )}
        {response.reason_code && (
          <p className="answer-panel__reason-code">
            {reasonLabels[response.reason_code] ?? response.reason_code}
          </p>
        )}
      </div>

      <div className="answer-panel__sources">
        <h3>Evidence used</h3>
        {response.sources.length ? (
          <ol>
            {response.sources.map((source) => (
              <EvidenceSource key={`${source.source_id}-${source.passage}`} source={source} />
            ))}
          </ol>
        ) : (
          <p className="answer-panel__secondary">
            {response.reason_code === "INSUFFICIENT_EVIDENCE"
              ? "No relevant source was found for this question."
              : "This route did not require retrieved evidence."}
          </p>
        )}
      </div>

      {ticket && <ReviewPanel key={ticket.id} ticket={ticket} busy={reviewBusy}
        error={reviewError} onReview={onReview} />}
    </section>
  );
}
