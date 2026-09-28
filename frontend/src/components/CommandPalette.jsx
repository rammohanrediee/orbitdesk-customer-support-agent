import { useEffect, useMemo, useRef, useState } from "react";
import { CornerDownLeft, Search, X } from "lucide-react";

export default function CommandPalette({
  open,
  questions,
  onClose,
  onChoose,
}) {
  const dialogRef = useRef(null);
  const inputRef = useRef(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const filteredQuestions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return questions;
    return questions.filter((question) =>
      question.toLowerCase().includes(normalized),
    );
  }, [query, questions]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      window.requestAnimationFrame(() => inputRef.current?.focus());
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) =>
        Math.min(current + 1, filteredQuestions.length - 1),
      );
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    }
    if (event.key === "Enter" && filteredQuestions[activeIndex]) {
      event.preventDefault();
      onChoose(filteredQuestions[activeIndex]);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="command-dialog"
      aria-labelledby="command-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
    >
      <div className="command-dialog__surface">
        <div className="command-dialog__field">
          <Search aria-hidden="true" size={18} />
          <label className="sr-only" htmlFor="command-search">
            Search example support questions
          </label>
          <input
            ref={inputRef}
            id="command-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search support questions"
            autoComplete="off"
          />
          <button
            className="icon-button"
            type="button"
            aria-label="Close command palette"
            onClick={onClose}
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        <div className="command-dialog__body">
          <h2 id="command-title">Example questions</h2>
          <p className="command-dialog__count" aria-live="polite">
            {filteredQuestions.length} available
          </p>
          <div role="listbox" aria-label="Example questions">
            {filteredQuestions.map((question, index) => (
              <button
                key={question}
                type="button"
                className="command-dialog__option"
                data-active={index === activeIndex}
                role="option"
                aria-selected={index === activeIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => onChoose(question)}
              >
                <span>{question}</span>
                <CornerDownLeft aria-hidden="true" size={16} />
              </button>
            ))}
            {filteredQuestions.length === 0 && (
              <p className="command-dialog__empty">
                No matching examples. Write your own question in the workspace.
              </p>
            )}
          </div>
        </div>

        <div className="command-dialog__footer" aria-hidden="true">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> choose</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </dialog>
  );
}
