import { useEffect, useMemo, useRef, useState } from "react";
import { CornerDownLeft, Search, X } from "lucide-react";

export default function CommandPalette({
  open,
  tickets,
  onClose,
  onChoose,
}) {
  const dialogRef = useRef(null);
  const inputRef = useRef(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const filteredTickets = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return tickets;
    return tickets.filter((ticket) =>
      ticket.question.toLowerCase().includes(normalized),
    );
  }, [query, tickets]);

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

  function moveActiveIndex(offset) {
    if (filteredTickets.length === 0) return;
    setActiveIndex((current) => Math.min(
      Math.max(current + offset, 0),
      filteredTickets.length - 1,
    ));
  }

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActiveIndex(1);
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActiveIndex(-1);
    }
    if (event.key === "Enter" && filteredTickets[activeIndex]) {
      event.preventDefault();
      onChoose(filteredTickets[activeIndex]);
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
            Search request history
          </label>
          <input
            ref={inputRef}
            id="command-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search request history"
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
          <h2 id="command-title">Request history</h2>
          <p className="command-dialog__count" aria-live="polite">
            {filteredTickets.length} available
          </p>
          <div role="listbox" aria-label="Request history">
            {filteredTickets.map((ticket, index) => (
              <button
                key={ticket.id}
                type="button"
                className="command-dialog__option"
                data-active={index === activeIndex}
                role="option"
                aria-selected={index === activeIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => onChoose(ticket)}
              >
                <span>{ticket.question}</span>
                <CornerDownLeft aria-hidden="true" size={16} />
              </button>
            ))}
            {filteredTickets.length === 0 && (
              <p className="command-dialog__empty">
                {tickets.length === 0
                  ? "No requests yet. Completed questions appear here."
                  : "No matching requests."}
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
