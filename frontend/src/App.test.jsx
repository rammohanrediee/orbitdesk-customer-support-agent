import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import { askSupport, getHealth } from "./api.js";

vi.mock("./api.js", () => ({
  askSupport: vi.fn(),
  getHealth: vi.fn(),
}));

afterEach(cleanup);

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

describe("OrbitDesk workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getHealth.mockResolvedValue({
      status: "ready",
      model: "z-ai/glm-4.5-air",
      api_key_configured: true,
    });
  });

  it("shows provider readiness and an empty answer state", async () => {
    render(<App />);

    expect(screen.getByRole("heading", {
      name: "Find the answer. Keep the evidence.",
    })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No answer yet" })).toBeInTheDocument();
    expect(await screen.findByText("API ready")).toBeInTheDocument();
  });

  it("loads an example question and renders the grounded result", async () => {
    const user = userEvent.setup();
    askSupport.mockResolvedValue(groundedResult);
    render(<App />);

    await user.click(screen.getByRole("button", {
      name: "Can a Viewer create an OrbitDesk API credential?",
    }));
    await user.click(screen.getByRole("button", { name: "Ask OrbitDesk" }));

    await waitFor(() => {
      expect(askSupport).toHaveBeenCalledWith({
        question: "Can a Viewer create an OrbitDesk API credential?",
        retrieval: "keyword",
      });
    });
    expect(await screen.findByText(
      "Only Owners and Admins can create API credentials.",
    )).toBeInTheDocument();
    expect(screen.getByText("92% confidence")).toBeInTheDocument();
  });
});
