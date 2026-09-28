import {
  BookMarked,
  CircleAlert,
  Quote,
  ShieldCheck,
} from "lucide-react";

function classificationLabel(classification) {
  return classification?.replaceAll("_", " ") ?? "waiting";
}

export default function AnswerPanel({ result, status, error }) {
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
        <span className="answer-panel__confidence">
          {Math.round(response.confidence * 100)}% confidence
        </span>
      </header>

      <div className="answer-panel__body">
        <h2>Grounded answer</h2>
        <p className="answer-panel__answer">{response.answer}</p>
        {response.clarification_question && (
          <p className="answer-panel__clarification">
            {response.clarification_question}
          </p>
        )}
      </div>

      <div className="answer-panel__sources">
        <h3>Evidence used</h3>
        {response.sources.length ? (
          <ol>
            {response.sources.map((source) => (
              <li key={`${source.source_id}-${source.passage}`}>
                <div>
                  <code>{source.source_id}</code>
                  <p>“{source.passage}”</p>
                </div>
                <Quote aria-hidden="true" size={15} />
              </li>
            ))}
          </ol>
        ) : (
          <p className="answer-panel__secondary">
            This route did not require retrieved evidence.
          </p>
        )}
      </div>
    </section>
  );
}
