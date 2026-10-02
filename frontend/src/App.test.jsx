import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import { createTicket, getDemoQuestions, getEvidence, getHealth, listTickets, reviewTicket, setOperatorToken } from "./api.js";

vi.mock("./api.js", () => ({
  createTicket: vi.fn(),
  getDemoQuestions: vi.fn(),
  getEvidence: vi.fn(),
  getHealth: vi.fn(),
  listTickets: vi.fn(),
  reviewTicket: vi.fn(),
  setOperatorToken: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const groundedResult = {
  response: {
    classification: "answerable",
    answer: "Only Owners and Admins can create API credentials.",
    sources: [
      {
        source_id: "KB-005",
        passage: "Only Owners and Admins can create API credentials.",
      },
    ],
    confidence: 0.92,
    clarification_question: null,
  },
  execution_log: ["triage", "retrieve:keyword", "generate", "verify:passed"],
  retrieval_mode: "keyword",
  model: "z-ai/glm-4.5-air",
  trace: { trace_id: "trace-test", events: [] },
  latency_seconds: 0.25,
};

const pendingTicket = {
  id: "ticket-1",
  question: "Can a Viewer create an OrbitDesk API credential?",
  generated_result: groundedResult,
  status: "pending",
  final_answer: null,
  review_note: null,
};

describe("OrbitDesk workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getHealth.mockResolvedValue({
      status: "ready",
      model: "z-ai/glm-4.5-air",
      api_key_configured: true,
    });
    listTickets.mockResolvedValue([]);
    getDemoQuestions.mockResolvedValue([]);
  });

  it("shows provider readiness and an empty answer state", async () => {
    render(<App />);

    expect(screen.getByRole("heading", {
      name: "Find the answer. Keep the evidence.",
    })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No answer yet" })).toBeInTheDocument();
    expect(screen.getByText("No requests yet")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Retrieval" }))
      .not.toBeInTheDocument();
    expect(await screen.findByText("API ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open OrbitDesk documentation" }))
      .toHaveAttribute("href", "/docs/");
  });

  it("keeps history before the workflow in the document order when open", async () => {
    render(<App />);

    expect(screen.getByRole("main").previousElementSibling)
      .toBe(screen.getByRole("complementary", { name: "Request history" }));
  });

  it("starts with mobile history closed and opens it on request", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("matchMedia", vi.fn((query) => ({
      matches: query.startsWith("(max-width"),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
    render(<App />);

    expect(screen.queryByRole("complementary", { name: "Request history" }))
      .not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show request history" }));
    expect(screen.getByRole("complementary", { name: "Request history" }))
      .toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: "Request history" }))
      .not.toBeInTheDocument();
  });

  it("explains API configuration problems without a hover tooltip", async () => {
    getHealth.mockResolvedValue({ status: "configuration_required", model: "z-ai/glm-4.5-air" });
    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Check the OpenRouter key and retrieval mode before asking a question.",
    );
    expect(screen.getByText("API issue")).toBeInTheDocument();
  });

  it("requires an operator token before loading private tickets", async () => {
    const user = userEvent.setup();
    getHealth.mockResolvedValue({ status: "ready", auth_required: true, model: "recorded-demo" });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Operator access" })).toBeInTheDocument();
    expect(listTickets).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Operator access token"), "shared-test-token");
    await user.click(screen.getByRole("button", { name: "Unlock workspace" }));

    await waitFor(() => expect(listTickets).toHaveBeenCalledTimes(1));
    expect(setOperatorToken).toHaveBeenCalledWith("shared-test-token");
    expect(await screen.findByRole("heading", { name: "Find the answer. Keep the evidence." }))
      .toBeInTheDocument();
  });

  it("keeps the workspace locked after an invalid operator token", async () => {
    const user = userEvent.setup();
    getHealth.mockResolvedValue({ status: "ready", auth_required: true, model: "recorded-demo" });
    listTickets.mockRejectedValue(new Error("Operator access required."));
    render(<App />);
    await user.type(await screen.findByLabelText("Operator access token"), "wrong");
    await user.click(screen.getByRole("button", { name: "Unlock workspace" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Operator access required.");
    expect(screen.queryByRole("heading", { name: "Find the answer. Keep the evidence." }))
      .not.toBeInTheDocument();
  });

  it("submits a question and saves a ticket for review", async () => {
    const user = userEvent.setup();
    createTicket.mockResolvedValue(pendingTicket);
    render(<App />);

    const question = screen.getByRole("textbox", { name: "Ask about OrbitDesk" });
    await user.type(question, "Can a Viewer create an OrbitDesk API credential?");
    await user.click(screen.getByRole("button", { name: "Ask OrbitDesk" }));

    await waitFor(() => {
      expect(createTicket).toHaveBeenCalledWith({
        question: "Can a Viewer create an OrbitDesk API credential?",
      });
    });
    expect(await screen.findByText(
      "Only Owners and Admins can create API credentials.",
    )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve answer" })).toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: "Can a Viewer create an OrbitDesk API credential?",
    })).toBeInTheDocument();
  });

  it("loads saved tickets and records a review decision", async () => {
    const user = userEvent.setup();
    listTickets.mockResolvedValue([pendingTicket]);
    reviewTicket.mockResolvedValue({
      ...pendingTicket,
      status: "approved",
      final_answer: groundedResult.response.answer,
    });
    render(<App />);

    expect(await screen.findByRole("button", {
      name: "Can a Viewer create an OrbitDesk API credential?",
    })).toBeInTheDocument();
    await user.click(screen.getByRole("button", {
      name: "Can a Viewer create an OrbitDesk API credential?",
    }));
    expect(screen.getByText(groundedResult.response.answer)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve answer" }));
    await waitFor(() => expect(reviewTicket).toHaveBeenCalledWith("ticket-1", {
      action: "approve",
    }));
    expect(await screen.findByText("Approved")).toBeInTheDocument();
  });

  it("lets a reviewer edit a generated answer", async () => {
    const user = userEvent.setup();
    listTickets.mockResolvedValue([pendingTicket]);
    reviewTicket.mockResolvedValue({
      ...pendingTicket,
      status: "edited",
      final_answer: "A reviewer corrected this answer.",
    });
    render(<App />);
    await user.click(await screen.findByRole("button", { name: pendingTicket.question }));
    await user.click(screen.getByRole("button", { name: "Edit answer" }));
    await user.clear(screen.getByRole("textbox", { name: "Final answer" }));
    await user.type(screen.getByRole("textbox", { name: "Final answer" }),
      "A reviewer corrected this answer.");
    await user.click(screen.getByRole("button", { name: "Save edited answer" }));

    await waitFor(() => expect(reviewTicket).toHaveBeenCalledWith("ticket-1", {
      action: "edit",
      answer: "A reviewer corrected this answer.",
    }));
    expect(await screen.findByText("Edited")).toBeInTheDocument();
  });

  it("opens the full cited source and explains human escalation", async () => {
    const user = userEvent.setup();
    listTickets.mockResolvedValue([{
      ...pendingTicket,
      generated_result: {
        ...groundedResult,
        response: {
          ...groundedResult.response,
          classification: "requires_escalation",
          requires_human: true,
          reason_code: "POLICY_REQUIRES_HUMAN",
          reason: "Repeated failures need the Connectors team.",
        },
      },
    }]);
    getEvidence.mockResolvedValue({
      source_id: "KB-005",
      title: "API Credentials",
      text: "Full document: Only Owners and Admins can create API credentials.",
    });
    render(<App />);
    await user.click(await screen.findByRole("button", {
      name: "Can a Viewer create an OrbitDesk API credential?",
    }));

    expect(screen.getByText(/Human review required: Repeated failures need the Connectors team/))
      .toBeInTheDocument();
    expect(screen.getByText("Policy requires a person")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View full source KB-005" }));
    expect(await screen.findByText(
      "Full document: Only Owners and Admins can create API credentials.",
    )).toBeInTheDocument();
    expect(getEvidence).toHaveBeenCalledWith("KB-005");
  });

  it("offers recorded questions when the API is in demo mode", async () => {
    const user = userEvent.setup();
    getHealth.mockResolvedValue({ status: "ready", model: "recorded-demo", demo_mode: true });
    getDemoQuestions.mockResolvedValue([{
      question_id: "Q-002",
      question: "I am a Viewer. Can I create an API credential?",
    }]);
    render(<App />);

    expect(await screen.findByText("I am a Viewer. Can I create an API credential?"))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use sample 1" }));
    expect(screen.getByRole("textbox", { name: "Ask about OrbitDesk" }))
      .toHaveValue("I am a Viewer. Can I create an API credential?");
    expect(screen.getByRole("textbox", { name: "Ask about OrbitDesk" }))
      .toHaveFocus();
    expect(screen.getByRole("heading", { name: "Try a recorded question" }))
      .toBeInTheDocument();
  });

  it("collapses and expands request history", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", {
      name: "Hide request history",
    }));
    expect(screen.queryByRole("complementary", { name: "Request history" }))
      .not.toBeInTheDocument();

    await user.click(screen.getByRole("button", {
      name: "Show request history",
    }));
    expect(screen.getByRole("complementary", { name: "Request history" }))
      .toBeInTheDocument();
  });

  it("opens empty request history search without seeded questions", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", {
      name: "Open request history search",
    }));
    expect(screen.getByText("No requests yet. Completed questions appear here."))
      .toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
