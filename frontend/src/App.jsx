import { useEffect, useState } from "react";
import {
  Activity,
  CircleDot,
  Command,
  Search,
  SquareArrowOutUpRight,
} from "lucide-react";
import { askSupport, getHealth } from "./api.js";
import AnswerPanel from "./components/AnswerPanel.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import HistoryRail from "./components/HistoryRail.jsx";
import Inspector from "./components/Inspector.jsx";
import QuestionComposer from "./components/QuestionComposer.jsx";

const EXAMPLE_QUESTIONS = [
  "Can a Viewer create an OrbitDesk API credential?",
  "Which timezone controls a scheduled export?",
  "A connection refresh failed. What details should support collect?",
  "Two exports returned render_failed after documented checks. What next?",
  "What information is safe to include in an escalation?",
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [retrieval, setRetrieval] = useState("keyword");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHealth({ signal: controller.signal })
      .then(setHealth)
      .catch(() => setHealth(null));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  function chooseQuestion(nextQuestion) {
    setQuestion(nextQuestion);
    setStatus("idle");
    setError("");
    setCommandOpen(false);
    window.requestAnimationFrame(() => {
      document.getElementById("support-question")?.focus();
    });
  }

  function updateQuestion(nextQuestion) {
    setQuestion(nextQuestion);
    if (status === "success" || status === "error") setStatus("idle");
    if (error) setError("");
  }

  async function submitQuestion() {
    setStatus("loading");
    setError("");
    try {
      const nextResult = await askSupport({
        question: question.trim(),
        retrieval,
      });
      setResult(nextResult);
      setStatus("success");
    } catch (requestError) {
      setStatus("error");
      setError(requestError.message);
    }
  }

  const serviceReady = health?.status === "ready";

  return (
    <div className="app-shell">
      <header className="product-nav">
        <div className="product-nav__inner">
          <a className="wordmark" href="#workspace" aria-label="OrbitDesk home">
            <span className="wordmark__mark" aria-hidden="true">O</span>
            <span>OrbitDesk</span>
          </a>

          <button
            className="search-trigger"
            type="button"
            onClick={() => setCommandOpen(true)}
            aria-label="Open example question search"
          >
            <Search aria-hidden="true" size={17} />
            <span>Search questions</span>
            <span className="search-trigger__shortcut" aria-hidden="true">
              <kbd>⌘</kbd><kbd>K</kbd>
            </span>
          </button>

          <div className="product-nav__tools">
            <div
              className="service-state"
              data-ready={serviceReady}
              title={
                serviceReady
                  ? "OpenRouter is configured"
                  : "OpenRouter configuration is required"
              }
            >
              <CircleDot aria-hidden="true" size={15} />
              <span>{serviceReady ? "API ready" : "Check API"}</span>
            </div>
            <a
              className="icon-button"
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              aria-label="Open API documentation"
              title="Open API documentation"
            >
              <SquareArrowOutUpRight aria-hidden="true" size={18} />
            </a>
          </div>
        </div>
      </header>

      <div className="workspace-grid" id="workspace">
        <HistoryRail questions={EXAMPLE_QUESTIONS} onChoose={chooseQuestion} />

        <main className="support-workspace">
          <div className="support-workspace__intro">
            <div>
              <p className="workspace-context">
                <Activity aria-hidden="true" size={15} /> Grounded support
              </p>
              <h1>Find the answer. Keep the evidence.</h1>
            </div>
            <p>
              OrbitDesk retrieves the local product record, asks the configured
              model, and verifies each cited passage before returning an answer.
            </p>
          </div>

          <QuestionComposer
            question={question}
            retrieval={retrieval}
            status={status}
            onQuestionChange={updateQuestion}
            onRetrievalChange={setRetrieval}
            onSubmit={submitQuestion}
          />

          <AnswerPanel result={result} status={status} error={error} />
        </main>

        <Inspector result={result} />
      </div>

      <footer className="status-footer">
        <span>OrbitDesk support workspace</span>
        <span aria-hidden="true">·</span>
        <span>Grounded citations</span>
        <span aria-hidden="true">·</span>
        <span className="status-footer__model">
          <Command aria-hidden="true" size={13} />
          {health?.model ?? "z-ai/glm-4.5-air"}
        </span>
      </footer>

      <CommandPalette
        open={commandOpen}
        questions={EXAMPLE_QUESTIONS}
        onClose={() => setCommandOpen(false)}
        onChoose={chooseQuestion}
      />
    </div>
  );
}
