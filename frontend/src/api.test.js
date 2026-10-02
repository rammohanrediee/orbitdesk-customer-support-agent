import { afterEach, expect, it, vi } from "vitest";
import { listTickets, setOperatorToken } from "./api.js";

afterEach(() => {
  setOperatorToken("");
  vi.unstubAllGlobals();
});

it("sends the operator token as a header and never in the URL", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  setOperatorToken("  demo-secret  ");

  await listTickets();

  expect(fetchMock.mock.calls[0][0]).toBe("/api/tickets");
  expect(fetchMock.mock.calls[0][1].headers.get("X-OrbitDesk-Token"))
    .toBe("demo-secret");
});
