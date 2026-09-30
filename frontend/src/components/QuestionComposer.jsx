import { Check, LoaderCircle, Send, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";

export default function QuestionComposer({
  question,
  retrieval,
  status,
  onQuestionChange,
  onRetrievalChange,
  onSubmit,
}) {
  const helperId = useId();
  const [touched, setTouched] = useState(false);
  const invalid = touched && question.trim().length < 3;
  const loading = status === "loading";

  const buttonState = invalid
    ? "error"
    : status === "success"
      ? "success"
      : status;

  let buttonIcon = <Send aria-hidden="true" size={17} />;
  let buttonLabel = "Ask OrbitDesk";
  if (buttonState === "loading") {
    buttonIcon = <LoaderCircle className="spinner" aria-hidden="true" size={17} />;
    buttonLabel = "Checking sources…";
  } else if (buttonState === "error") {
    buttonIcon = <TriangleAlert aria-hidden="true" size={17} />;
  } else if (buttonState === "success") {
    buttonIcon = <Check aria-hidden="true" size={17} />;
    buttonLabel = "Answer ready";
  }

  function handleSubmit(event) {
    event.preventDefault();
    setTouched(true);
    if (question.trim().length >= 3 && !loading) onSubmit();
  }

  function handleKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      handleSubmit(event);
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit} noValidate>
      <div className="composer__field">
        <label htmlFor="support-question">Ask about OrbitDesk</label>
        <textarea
          id="support-question"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          onBlur={() => setTouched(true)}
          onKeyDown={handleKeyDown}
          aria-invalid={invalid}
          aria-describedby={helperId}
          placeholder="For example: Can a Viewer create an API credential?"
          rows={4}
        />
        <p
          id={helperId}
          className="composer__helper"
          data-tone={invalid ? "error" : "neutral"}
        >
          {invalid
            ? "The question is too short. Add the feature or problem you need help with."
            : "Use a product feature, visible symptom, or documented error code."}
        </p>
      </div>

      <div className="composer__actions">
        <label className="retrieval-control">
          <span>Retrieval</span>
          <select
            value={retrieval}
            onChange={(event) => onRetrievalChange(event.target.value)}
            disabled={loading}
          >
            <option value="keyword">Keyword</option>
            <option value="semantic">Semantic</option>
          </select>
        </label>

        <span className="composer__shortcut" aria-hidden="true">
          <kbd>⌘</kbd><kbd>↵</kbd>
        </span>

        <button
          className="composer__submit"
          type="submit"
          disabled={loading || question.trim().length < 3}
          data-state={buttonState}
          aria-busy={loading}
        >
          {buttonIcon}
          <span>{buttonLabel}</span>
        </button>
      </div>
    </form>
  );
}
