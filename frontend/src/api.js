const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 65_000;

async function parseError(response) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // The safe generic message below covers non-JSON responses.
  }
  return "The support service could not complete this request. Try again.";
}

export async function getHealth({ signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/api/health`, { signal });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function askSupport({ question, retrieval }) {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  try {
    const response = await fetch(`${API_BASE_URL}/api/support`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, retrieval }),
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    return response.json();
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
