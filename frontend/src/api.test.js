import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { askSupport, getHealth } from "./api.js";

function jsonResponse(payload, { ok = true } = {}) {
  return {
    ok,
    json: vi.fn().mockResolvedValue(payload),
  };
}

describe("support API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reads API health with the provided abort signal", async () => {
    const signal = new AbortController().signal;
    fetch.mockResolvedValue(jsonResponse({ status: "ready" }));

    await expect(getHealth({ signal })).resolves.toEqual({ status: "ready" });
    expect(fetch).toHaveBeenCalledWith("/api/health", { signal });
  });

  it("sends the question and retrieval mode as JSON", async () => {
    fetch.mockResolvedValue(jsonResponse({ response: { answer: "Grounded" } }));

    await expect(askSupport({
      question: "Who can create credentials?",
      retrieval: "keyword",
    })).resolves.toEqual({ response: { answer: "Grounded" } });

    expect(fetch).toHaveBeenCalledWith("/api/support", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "Who can create credentials?",
        retrieval: "keyword",
      }),
    }));
  });

  it("surfaces a safe API error detail", async () => {
    fetch.mockResolvedValue(jsonResponse(
      { detail: "Semantic retrieval is not installed on this server." },
      { ok: false },
    ));

    await expect(askSupport({
      question: "Find a semantic match",
      retrieval: "semantic",
    })).rejects.toThrow("Semantic retrieval is not installed on this server.");
  });

  it("uses a safe error when a successful response is not JSON", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockRejectedValue(new SyntaxError("invalid JSON")),
    });

    await expect(getHealth()).rejects.toThrow(
      "The support service could not complete this request. Try again.",
    );
  });

  it("aborts support requests at the client deadline", async () => {
    vi.useFakeTimers();
    fetch.mockImplementation((_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      });
    }));

    const request = askSupport({
      question: "Why did this request take too long?",
      retrieval: "keyword",
    });
    const rejection = expect(request).rejects.toThrow(
      "The support request reached its time limit. Try a shorter question.",
    );

    await vi.advanceTimersByTimeAsync(65_000);
    await rejection;
  });
});
