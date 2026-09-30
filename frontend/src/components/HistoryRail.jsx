import { BookOpenText, Clock3, MessageSquareText } from "lucide-react";

export default function HistoryRail({ questions, onChoose }) {
  return (
    <aside
      className="history-rail"
      id="request-history"
      aria-label="Request history"
    >
      <div className="history-rail__heading">
        <div>
          <p>Workspace</p>
          <h2>Request history</h2>
        </div>
        <MessageSquareText aria-hidden="true" size={18} />
      </div>

      <nav aria-label="Previous support requests">
        <p className="rail-label"><Clock3 aria-hidden="true" size={14} /> Recent</p>
        {questions.length === 0 && (
          <p className="history-empty">No requests yet</p>
        )}
        <ul className="history-list">
          {questions.map((question) => (
            <li key={question}>
              <button type="button" onClick={() => onChoose(question)}>
                {question}
              </button>
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
