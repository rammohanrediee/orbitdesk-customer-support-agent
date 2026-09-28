import { BookOpenText, Clock3, MessageSquareText } from "lucide-react";

export default function HistoryRail({ questions, onChoose }) {
  return (
    <aside className="history-rail" aria-label="Question examples">
      <div className="history-rail__heading">
        <div>
          <p>Workspace</p>
          <h2>Support desk</h2>
        </div>
        <MessageSquareText aria-hidden="true" size={18} />
      </div>

      <nav aria-label="Example support questions">
        <p className="rail-label"><Clock3 aria-hidden="true" size={14} /> Examples</p>
        <ul className="history-list">
          {questions.slice(0, 4).map((question) => (
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
