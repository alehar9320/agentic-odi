import { describe, expect, it, vi } from "vitest";

import {
  CACHE_PREFIX,
  NAVIGATION_TIMEOUT_MS,
  OFFLINE_URL,
  respondToApi,
  respondToAsset,
  respondToNavigation,
  routeRequest,
  SERVICE_WORKER_URL,
  SHELL_URL,
  cacheName,
  isApiRequest,
  isNavigationRequest,
  isPrecached,
} from "./swRouting";

const ORIGIN = "https://studio.example";

function url(path: string, origin = ORIGIN): URL {
  return new URL(path, origin);
}

const PRECACHE = new Set(["/", "/index.html", "/offline.html", "/favicon.svg", "/assets/app-abc.js"]);

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

  it("answers a failed navigation from the precached shell document", () => {
    expect(SHELL_URL).toBe("/index.html");
  });

  it("bounds a navigation at three seconds before the cache answers", () => {
    expect(NAVIGATION_TIMEOUT_MS).toBe(3_000);
  });
});

describe("the cache name", () => {
  it("moves with the build, so activate can retire the previous one", () => {
    expect(cacheName("abc123")).toBe("studio-shell-abc123");
    expect(cacheName("def456")).not.toBe(cacheName("abc123"));
  });

  it("keeps one prefix, so old caches are found without guessing", () => {
    expect(cacheName("abc123").startsWith(CACHE_PREFIX)).toBe(true);
  });
});

describe("isPrecached", () => {
  it("claims a manifest entry on this origin", () => {
    expect(isPrecached(url("/index.html"), ORIGIN, PRECACHE)).toBe(true);
    expect(isPrecached(url("/favicon.svg"), ORIGIN, PRECACHE)).toBe(true);
  });

  it("claims a hashed asset even when the manifest is missing it", () => {
    expect(isPrecached(url("/assets/index-other.js"), ORIGIN, PRECACHE)).toBe(true);
  });

  it("leaves a non-hashed path the manifest does not list", () => {
    expect(isPrecached(url("/records/42"), ORIGIN, PRECACHE)).toBe(false);
    expect(isPrecached(url("/index.html"), "https://elsewhere.example", PRECACHE)).toBe(false);
  });
});

describe("routeRequest", () => {
  const get = { method: "GET", mode: "cors" };
  const navigate = { method: "GET", mode: "navigate" };
  const context = { origin: ORIGIN, precache: PRECACHE };

  it("sends every /api request to the network, never a cache", () => {
    expect(routeRequest(url("/api/canvas"), get, context)).toBe("api");
    expect(routeRequest(url("/api/jobs/1"), navigate, context)).toBe("api");
  });

  it("treats a top-level GET as a navigation", () => {
    expect(routeRequest(url("/records/42"), navigate, context)).toBe("navigation");
    expect(routeRequest(url("/"), navigate, context)).toBe("navigation");
  });

  it("serves a hashed asset cache-first", () => {
    expect(routeRequest(url("/assets/app-abc.js"), get, context)).toBe("asset");
  });

  it("leaves anything else to the browser", () => {
    expect(routeRequest(url("/records/42"), get, context)).toBe("other");
    expect(routeRequest(url("/api/canvas"), { method: "POST", mode: "cors" }, context)).toBe("api");
  });
});

describe("respondToApi", () => {
  const request = new Request("https://studio.example/api/canvas");

  it("asks the network, so no API response is ever served from cache", async () => {
    const response = new Response("{}");
    const fetchNetwork = vi.fn().mockResolvedValue(response);

    const answer = await respondToApi(request, { fetchNetwork });

    expect(answer).toBe(response);
    expect(fetchNetwork).toHaveBeenCalledWith(request);
  });

  it("fails fast when the network is gone rather than hanging", async () => {
    const fetchNetwork = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(respondToApi(request, { fetchNetwork })).rejects.toThrow("Failed to fetch");
  });
});

describe("respondToAsset", () => {
  const request = new Request("https://studio.example/assets/app-abc.js");

  it("answers from the cache without touching the network on a hit", async () => {
    const cached = new Response("cached");
    const readCache = vi.fn().mockResolvedValue(cached);
    const fetchNetwork = vi.fn();

    const answer = await respondToAsset(request, { readCache, fetchNetwork });

    expect(answer).toBe(cached);
    expect(fetchNetwork).not.toHaveBeenCalled();
  });

  it("falls back to the network on a miss", async () => {
    const fresh = new Response("fresh");
    const readCache = vi.fn().mockResolvedValue(undefined);
    const fetchNetwork = vi.fn().mockResolvedValue(fresh);

    const answer = await respondToAsset(request, { readCache, fetchNetwork });

    expect(answer).toBe(fresh);
    expect(fetchNetwork).toHaveBeenCalledWith(request);
  });
});

describe("respondToNavigation", () => {
  const request = new Request("https://studio.example/workspace", { method: "GET" });

  it("serves the network response when the shell answers", async () => {
    const shell = new Response("<html>shell</html>");
    const fetchShell = vi.fn().mockResolvedValue(shell);
    const readShell = vi.fn();
    const readOfflinePage = vi.fn();

    const response = await respondToNavigation(request, { fetchShell, readShell, readOfflinePage });

    expect(response).toBe(shell);
    expect(readShell).not.toHaveBeenCalled();
    expect(readOfflinePage).not.toHaveBeenCalled();
  });

  it("serves the cached shell when the network is unreachable", async () => {
    const cachedShell = new Response("<html>cached shell</html>");
    const fetchShell = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const readShell = vi.fn().mockResolvedValue(cachedShell);
    const readOfflinePage = vi.fn();

    const response = await respondToNavigation(request, { fetchShell, readShell, readOfflinePage });

    expect(response).toBe(cachedShell);
    expect(readOfflinePage).not.toHaveBeenCalled();
  });

  it("falls through to the offline page when the shell cache was evicted", async () => {
    const offline = new Response("<html>offline</html>");
    const fetchShell = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const readShell = vi.fn().mockResolvedValue(undefined);
    const readOfflinePage = vi.fn().mockResolvedValue(offline);

    const response = await respondToNavigation(request, { fetchShell, readShell, readOfflinePage });

    expect(response).toBe(offline);
    expect(readOfflinePage).toHaveBeenCalledTimes(1);
  });

  it("answers plainly when both the shell and the offline page were evicted", async () => {
    const fetchShell = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const readShell = vi.fn().mockResolvedValue(undefined);
    const readOfflinePage = vi.fn().mockResolvedValue(undefined);

    const response = await respondToNavigation(request, { fetchShell, readShell, readOfflinePage });

    expect(response.status).toBe(503);
  });

  it("serves the cached shell when the network hangs past the timeout", async () => {
    vi.useFakeTimers();
    try {
      const cachedShell = new Response("<html>cached shell</html>");
      // A request that never settles: the timeout is the only way out.
      const fetchShell = vi.fn().mockReturnValue(new Promise<Response>(() => {}));
      const readShell = vi.fn().mockResolvedValue(cachedShell);
      const readOfflinePage = vi.fn();

      const pending = respondToNavigation(request, { fetchShell, readShell, readOfflinePage });
      await vi.advanceTimersByTimeAsync(NAVIGATION_TIMEOUT_MS);

      const response = await pending;
      expect(response).toBe(cachedShell);
    } finally {
      vi.useRealTimers();
    }
  });
});
