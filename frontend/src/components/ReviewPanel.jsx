import { useState } from "react";

export default function ReviewPanel({ ticket, busy, error, onReview }) {
  const [mode, setMode] = useState(null);
  const [answer, setAnswer] = useState(ticket.generated_result.response.answer);
  const [note, setNote] = useState("");

  if (ticket.status !== "pending") {
    return (
      <section className="review-panel" aria-label="Review decision">
        <h3>Review decision</h3>
        <p className="review-panel__status">{ticket.status[0].toUpperCase() + ticket.status.slice(1)}</p>
        {ticket.final_answer && <p>{ticket.final_answer}</p>}
        {ticket.review_note && <p>{ticket.review_note}</p>}
      </section>
    );
  }

  return (
    <section className="review-panel" aria-label="Review decision">
      <h3>Review this draft</h3>
      <p>Check the answer and evidence before deciding what to send.</p>
      {error && <p role="alert" className="review-panel__error">{error}</p>}
      <div className="review-panel__actions">
        <button type="button" disabled={busy} onClick={() => onReview({ action: "approve" })}>
          Approve answer
        </button>
        <button type="button" disabled={busy} onClick={() => setMode("edit")}>
          Edit answer
        </button>
        <button type="button" disabled={busy} onClick={() => setMode("escalate")}>
          Escalate
        </button>
      </div>
      {mode === "edit" && (
        <form onSubmit={(event) => {
          event.preventDefault();
          if (answer.trim()) onReview({ action: "edit", answer: answer.trim() });
        }}>
          <label htmlFor="review-answer">Final answer</label>
          <textarea id="review-answer" value={answer} maxLength={2000}
            onChange={(event) => setAnswer(event.target.value)} />
          <button type="submit" disabled={busy || !answer.trim()}>Save edited answer</button>
        </form>
      )}
      {mode === "escalate" && (
        <form onSubmit={(event) => {
          event.preventDefault();
          if (note.trim()) onReview({ action: "escalate", note: note.trim() });
        }}>
          <label htmlFor="review-note">Reason for escalation</label>
          <textarea id="review-note" value={note} maxLength={2000}
            onChange={(event) => setNote(event.target.value)} />
          <button type="submit" disabled={busy || !note.trim()}>Send to human review</button>
        </form>
      )}
    </section>
  );
}
