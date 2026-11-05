import { describe, expect, it, vi } from "vitest";

import {
  isApiRequest,
  isNavigationRequest,
  OFFLINE_URL,
  respondToNavigation,
  SERVICE_WORKER_URL,
} from "./swRouting";

const ORIGIN = "https://studio.example";

function url(path: string, origin = ORIGIN): URL {
  return new URL(path, origin);
}

describe("isApiRequest", () => {
  it("claims the API on this origin, so the worker never caches it", () => {
    expect(isApiRequest(url("/api/canvas"), ORIGIN)).toBe(true);
    expect(isApiRequest(url("/api/health/llm"), ORIGIN)).toBe(true);
  });

  it("leaves the shell and the offline page alone", () => {
    expect(isApiRequest(url("/"), ORIGIN)).toBe(false);
    expect(isApiRequest(url("/offline.html"), ORIGIN)).toBe(false);
    expect(isApiRequest(url("/assets/index-abc.js"), ORIGIN)).toBe(false);
  });

  it("does not claim another origin's /api path", () => {
    expect(isApiRequest(url("/api/canvas", "https://elsewhere.example"), ORIGIN)).toBe(false);
  });
});

describe("isNavigationRequest", () => {
  it("claims a top-level GET navigation", () => {
    expect(isNavigationRequest({ method: "GET", mode: "navigate" })).toBe(true);
  });

  it("ignores subresources and non-GET requests", () => {
    expect(isNavigationRequest({ method: "GET", mode: "cors" })).toBe(false);
    expect(isNavigationRequest({ method: "POST", mode: "navigate" })).toBe(false);
  });
});

describe("the worker's fixed paths", () => {
  it("serves the offline page from the origin root", () => {
    expect(OFFLINE_URL).toBe("/offline.html");
  });

  it("registers the worker at the origin root so its scope is the whole app", () => {
    expect(SERVICE_WORKER_URL).toBe("/sw.js");
  });
});

describe("respondToNavigation", () => {
  const request = new Request("https://studio.example/workspace", { method: "GET" });

  it("serves the network response when the shell answers", async () => {
    const shell = new Response("<html>shell</html>");
    const fetchShell = vi.fn().mockResolvedValue(shell);
    const readOfflinePage = vi.fn();

    const response = await respondToNavigation(request, { fetchShell, readOfflinePage });

    expect(response).toBe(shell);
    expect(readOfflinePage).not.toHaveBeenCalled();
  });

  it("serves the cached offline page when the network is unreachable", async () => {
    const offline = new Response("<html>offline</html>");
    const fetchShell = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const readOfflinePage = vi.fn().mockResolvedValue(offline);

    const response = await respondToNavigation(request, { fetchShell, readOfflinePage });

    expect(response).toBe(offline);
    expect(readOfflinePage).toHaveBeenCalledTimes(1);
  });

  it("answers plainly when the offline page was evicted from the cache", async () => {
    const fetchShell = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const readOfflinePage = vi.fn().mockResolvedValue(undefined);

    const response = await respondToNavigation(request, { fetchShell, readOfflinePage });

    expect(response.status).toBe(503);
  });
});
