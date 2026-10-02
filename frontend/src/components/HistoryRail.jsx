import { BookOpenText } from "lucide-react";

export default function HistoryRail({ tickets, error, onChoose }) {
  return (
    <aside
      className="history-rail"
      id="request-history"
      aria-label="Request history"
    >
      <div className="history-rail__heading">
        <h2>Request history</h2>
      </div>

      <nav aria-label="Previous support requests">
        {error && <p className="history-empty" role="alert">{error}</p>}
        {tickets.length === 0 && (
          <p className="history-empty">No requests yet</p>
        )}
        <ul className="history-list">
          {tickets.map((ticket) => (
            <li key={ticket.id}>
              <button type="button" onClick={() => onChoose(ticket)}>
                {ticket.question}
              </button>
              <small>{ticket.status}</small>
            </li>
          ))}
        </ul>
      </nav>

      <div className="history-rail__note">
        <BookOpenText aria-hidden="true" size={17} />
        <p>
          Answers are limited to the checked-in OrbitDesk knowledge base and
          resolved cases.
        </p>
      </div>
    </aside>
  );
}
