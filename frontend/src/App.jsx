import { useEffect, useRef, useState } from "react";
import {
  CircleDot,
  Command,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  SquareArrowOutUpRight,
} from "lucide-react";
import { getDemoQuestions, getHealth, listTickets, setOperatorToken } from "./api.js";
import AnswerPanel from "./components/AnswerPanel.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import HistoryRail from "./components/HistoryRail.jsx";
import Inspector from "./components/Inspector.jsx";
import QuestionComposer from "./components/QuestionComposer.jsx";
import useTicketWorkflow from "./useTicketWorkflow.js";

const HISTORY_WIDTH_KEY = "orbitdesk.historyWidth";

function historyWidthLimits(viewportWidth) {
  const docked = viewportWidth >= 960;
  const min = docked ? 192 : 200;
  const available = docked
    ? viewportWidth - (viewportWidth >= 1440 ? 384 : 336) - 320
    : viewportWidth - 48;
  return {
    min,
    max: Math.max(min, Math.min(480, available)),
    initial: docked ? 224 : 320,
  };
}

function clampHistoryWidth(width, limits) {
  return Math.min(limits.max, Math.max(limits.min, width));
}

export default function App() {
  const {
    activeTicket,
    chooseTicket: selectTicket,
    decideReview,
    error,
    question,
    reviewBusy,
    reviewError,
    setTickets,
    status,
    submitQuestion,
    tickets,
    updateQuestion,
  } = useTicketWorkflow();
  const [historyOpen, setHistoryOpen] = useState(() =>
    typeof window.matchMedia === "function"
      ? window.matchMedia("(min-width: 60rem)").matches
      : true);
  const [viewportWidth, setViewportWidth] = useState(() => window.innerWidth);
  const [historyWidth, setHistoryWidth] = useState(() => {
    try {
      const saved = Number(window.localStorage.getItem(HISTORY_WIDTH_KEY));
      return Number.isFinite(saved) && saved >= 192 && saved <= 480 ? saved : null;
    } catch {
      return null;
    }
  });
  const resizePointer = useRef(null);
  const [historyError, setHistoryError] = useState("");
  const [health, setHealth] = useState(null);
  const [healthChecked, setHealthChecked] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [demoQuestions, setDemoQuestions] = useState([]);
  const [tokenDraft, setTokenDraft] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const widthLimits = historyWidthLimits(viewportWidth);
  const displayedHistoryWidth = clampHistoryWidth(
    historyWidth ?? widthLimits.initial,
    widthLimits,
  );

  useEffect(() => {
    const handleResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (historyWidth === null) return;
    try {
      window.localStorage.setItem(HISTORY_WIDTH_KEY, String(historyWidth));
    } catch {
      // The drawer remains resizable when storage is unavailable.
    }
  }, [historyWidth]);

  useEffect(() => {
    const controller = new AbortController();
    getHealth({ signal: controller.signal })
      .then((result) => {
        setHealth(result);
        if (!result.auth_required) {
          listTickets({ signal: controller.signal })
            .then(setTickets)
            .catch(() => setHistoryError("Saved tickets could not be loaded."));
        }
      })
      .catch(() => setHealth(null))
      .finally(() => {
        if (!controller.signal.aborted) setHealthChecked(true);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!health?.demo_mode) return undefined;
    const controller = new AbortController();
    getDemoQuestions({ signal: controller.signal })
      .then(setDemoQuestions)
      .catch(() => setDemoQuestions([]));
    return () => controller.abort();
  }, [health?.demo_mode]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const desktop = window.matchMedia("(min-width: 60rem)");
    const handleResize = () => setHistoryOpen(desktop.matches);
    desktop.addEventListener("change", handleResize);
    return () => desktop.removeEventListener("change", handleResize);
  }, []);

  useEffect(() => {
    if (!historyOpen) return undefined;
    const handleEscape = (event) => {
      if (event.key === "Escape") setHistoryOpen(false);
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [historyOpen]);

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

  function chooseTicket(ticket) {
    selectTicket(ticket);
    setCommandOpen(false);
    if (window.matchMedia?.("(max-width: 59.99rem)")?.matches) {
      setHistoryOpen(false);
    }
  }

  function startHistoryResize(event) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.preventDefault();
    resizePointer.current = {
      id: event.pointerId,
      x: event.clientX,
      width: displayedHistoryWidth,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function moveHistoryResize(event) {
    if (resizePointer.current?.id !== event.pointerId) return;
    setHistoryWidth(clampHistoryWidth(
      resizePointer.current.width + event.clientX - resizePointer.current.x,
      widthLimits,
    ));
  }

  function stopHistoryResize(event) {
    if (resizePointer.current?.id !== event.pointerId) return;
    resizePointer.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function resizeHistoryWithKeyboard(event) {
    let nextWidth;
    if (event.key === "ArrowLeft") nextWidth = displayedHistoryWidth - 16;
    if (event.key === "ArrowRight") nextWidth = displayedHistoryWidth + 16;
    if (event.key === "Home") nextWidth = widthLimits.min;
    if (event.key === "End") nextWidth = widthLimits.max;
    if (nextWidth === undefined) return;
    event.preventDefault();
    setHistoryWidth(clampHistoryWidth(nextWidth, widthLimits));
  }

  function chooseDemoQuestion(sampleQuestion) {
    updateQuestion(sampleQuestion);
    document.getElementById("support-question")?.focus();
  }

  async function unlockWorkspace(event) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    setOperatorToken(tokenDraft);
    try {
      setTickets(await listTickets());
      setAuthenticated(true);
      setTokenDraft("");
    } catch (requestError) {
      setOperatorToken("");
      setAuthError(requestError.message);
    } finally {
      setAuthBusy(false);
    }
  }

  if (health?.auth_required && !authenticated) {
    return (
      <div className="app-shell access-shell">
        <main className="access-panel">
          <span className="wordmark"><span className="wordmark__mark" aria-hidden="true">O</span> OrbitDesk</span>
          <h1>Operator access</h1>
          <p>Enter the demo operator token to view tickets and use the support workflow. It stays in this browser tab’s memory.</p>
          <form onSubmit={unlockWorkspace}>
            <label htmlFor="operator-token">Operator access token</label>
            <input id="operator-token" type="password" autoComplete="off" value={tokenDraft}
              onChange={(event) => setTokenDraft(event.target.value)} required />
            <button type="submit" disabled={authBusy}>{authBusy ? "Checking…" : "Unlock workspace"}</button>
          </form>
          {authError && <p role="alert">{authError}</p>}
        </main>
      </div>
    );
  }

  const serviceReady = health?.status === "ready";
  const serviceNotice = !healthChecked || serviceReady
    ? null
    : !health
      ? "OrbitDesk cannot reach the API. Start the API server, then reload this page."
      : health.status === "unavailable"
        ? "Ticket storage is unavailable. Check the API server logs before asking a question."
        : "The API needs configuration. Check the OpenRouter key and retrieval mode before asking a question.";

  return (
    <div className="app-shell">
      <header className="product-nav">
        <div className="product-nav__inner">
          <div className="product-nav__brand">
            <button
              className="icon-button history-toggle"
              type="button"
              aria-controls="request-history"
              aria-expanded={historyOpen}
              aria-label={historyOpen
                ? "Hide request history"
                : "Show request history"}
              title={historyOpen
                ? "Hide request history"
                : "Show request history"}
              onClick={() => setHistoryOpen((current) => !current)}
            >
              {historyOpen
                ? <PanelLeftClose aria-hidden="true" size={18} />
                : <PanelLeftOpen aria-hidden="true" size={18} />}
              <span className="history-toggle__label">History</span>
            </button>
            <a className="wordmark" href="#workspace" aria-label="OrbitDesk home">
              <span className="wordmark__mark" aria-hidden="true">O</span>
              <span>OrbitDesk</span>
            </a>
          </div>

          <button
            className="search-trigger"
            type="button"
            onClick={() => setCommandOpen(true)}
            aria-label="Open request history search"
          >
            <Search aria-hidden="true" size={17} />
            <span>Search history</span>
            <span className="search-trigger__shortcut" aria-hidden="true">
              <kbd>⌘</kbd><kbd>K</kbd>
            </span>
          </button>

          <div className="product-nav__tools">
            <div
              className="service-state"
              data-ready={serviceReady}
            >
              <CircleDot aria-hidden="true" size={15} />
              <span>{!healthChecked ? "Checking API" : serviceReady ? (health.demo_mode ? "Demo ready" : "API ready") : "API issue"}</span>
            </div>
            <a
              className="icon-button"
              href="/docs/"
              target="_blank"
              rel="noreferrer"
              aria-label="Open OrbitDesk documentation"
              title="Open OrbitDesk documentation"
            >
              <SquareArrowOutUpRight aria-hidden="true" size={18} />
            </a>
          </div>

        </div>
      </header>

      <div
        className="workspace-grid"
        id="workspace"
        data-history-open={historyOpen}
        style={{ "--history-width": `${displayedHistoryWidth}px` }}
      >
        {historyOpen && <>
          <button
            className="history-backdrop"
            type="button"
            aria-label="Dismiss request history"
            onClick={() => setHistoryOpen(false)}
          />
          <HistoryRail
            tickets={tickets}
            error={historyError}
            onChoose={chooseTicket}
            onClose={() => setHistoryOpen(false)}
          />
          <div
            className="history-resize"
            role="separator"
            tabIndex={0}
            aria-label="Resize request history"
            aria-controls="request-history"
            aria-orientation="vertical"
            aria-valuemin={widthLimits.min}
            aria-valuemax={widthLimits.max}
            aria-valuenow={displayedHistoryWidth}
            title="Drag to resize request history; use arrow keys when focused"
            onPointerDown={startHistoryResize}
            onPointerMove={moveHistoryResize}
            onPointerUp={stopHistoryResize}
            onPointerCancel={stopHistoryResize}
            onLostPointerCapture={() => { resizePointer.current = null; }}
            onKeyDown={resizeHistoryWithKeyboard}
          />
        </>}

        <main className="support-workspace">
          <div className="support-workspace__intro">
            <div>
              <h1>Find the answer. Keep the evidence.</h1>
            </div>
            <p>
              OrbitDesk retrieves the local product record, generates a support
              draft, and verifies each cited passage before returning it for review.
            </p>
          </div>

          {serviceNotice && <p className="service-notice" role="status">
            <CircleDot aria-hidden="true" size={18} />
            <span>{serviceNotice}</span>
          </p>}

          <QuestionComposer
            question={question}
            status={status}
            onQuestionChange={updateQuestion}
            onSubmit={submitQuestion}
          />

          {health?.demo_mode && (
            <section className="demo-questions" aria-label="Recorded demo questions">
              <h2>Try a recorded question</h2>
              <p>These questions use saved demo answers.</p>
              <ol>
                {demoQuestions.map((sample, index) => (
                  <li key={sample.question_id}>
                    <p>{sample.question}</p>
                    <button type="button" onClick={() => chooseDemoQuestion(sample.question)}>
                      Use sample {index + 1}
                    </button>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <AnswerPanel
            result={activeTicket?.generated_result ?? null}
            ticket={activeTicket}
            status={status}
            error={error}
            reviewError={reviewError}
            reviewBusy={reviewBusy}
            onReview={decideReview}
          />
        </main>

        <Inspector result={activeTicket?.generated_result ?? null} defaultModel={health?.model} />
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
        tickets={tickets}
        onClose={() => setCommandOpen(false)}
        onChoose={chooseTicket}
      />
    </div>
  );
}
