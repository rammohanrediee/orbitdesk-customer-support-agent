const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 65_000;
const GENERIC_ERROR = "The support service could not complete this request. Try again.";
let operatorToken = "";

export function setOperatorToken(token) {
  operatorToken = token?.trim() ?? "";
}

async function parseError(response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // The safe generic message below covers non-JSON responses.
  }
  return GENERIC_ERROR;
}

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers);
  if (operatorToken) headers.set("X-OrbitDesk-Token", operatorToken);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  try {
    return await response.json();
  } catch {
    throw new Error(GENERIC_ERROR);
  }
}

export function getHealth({ signal } = {}) {
  return requestJson("/api/health", { signal });
}

export function listTickets({ signal } = {}) {
  return requestJson("/api/tickets", { signal });
}

export function getEvidence(sourceId) {
  return requestJson(`/api/evidence/${encodeURIComponent(sourceId)}`);
}

export function getDemoQuestions({ signal } = {}) {
  return requestJson("/api/demo-questions", { signal });
}

export function reviewTicket(ticketId, decision) {
  return requestJson(`/api/tickets/${encodeURIComponent(ticketId)}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decision),
  });
}

export async function askSupport({ question }) {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  try {
    return await requestJson("/api/support", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "The support request reached its time limit. Try a shorter question.",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function createTicket({ question }) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await requestJson("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The support request reached its time limit. Try a shorter question.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
