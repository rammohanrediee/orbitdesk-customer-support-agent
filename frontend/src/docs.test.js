import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const html = readFileSync(resolve(process.cwd(), "docs/index.html"), "utf8");

describe("documentation workspace links", () => {
  it("opens the running chatbot instead of raw React HTML when docs are opened as a file", () => {
    const page = new JSDOM(html, {
      url: "file:///project/frontend/docs/index.html",
      runScripts: "dangerously",
    });

    const links = page.window.document.querySelectorAll("[data-workspace-link]");
    expect(links).toHaveLength(4);
    for (const link of links) {
      expect(link.href).toBe("http://127.0.0.1:5174/#workspace");
    }
  });

  it("keeps relative navigation when served by the app", () => {
    const page = new JSDOM(html, {
      url: "http://127.0.0.1:5174/docs/#exports",
      runScripts: "dangerously",
    });

    for (const link of page.window.document.querySelectorAll("[data-workspace-link]")) {
      expect(link.href).toBe("http://127.0.0.1:5174/index.html#workspace");
    }
  });
});
