/**
 * The routing rules the service worker applies to a request.
 *
 * They live outside `sw.ts` so they can be tested without a service-worker
 * global: `sw.ts` attaches listeners the moment it is imported, which a unit
 * test cannot provide.
 */

/** Where a navigation that cannot reach the network is sent instead. */
export const OFFLINE_URL = "/offline.html";

/** The path the worker is served from, and the path `main.tsx` registers. */
export const SERVICE_WORKER_URL = "/sw.js";

/**
 * The API is never intercepted, cached, or served from cache.
 *
 * A cached canvas response would defeat the browser BFF's fallback and the
 * conflict rules, so `/api/` requests bypass the worker entirely.
 */
export function isApiRequest(url: URL, origin: string): boolean {
  return url.origin === origin && url.pathname.startsWith("/api/");
}

/**
 * A top-level navigation, the only kind of request whose failure is a browser
 * error page rather than a screen the worker can improve on.
 */
export function isNavigationRequest(request: { method: string; mode: string }): boolean {
  return request.method === "GET" && request.mode === "navigate";
}

/** The collaborators the navigation handler needs, injected so a test can drive
 * the offline path without a service-worker global. */
export interface NavigationFallback {
  /** The real network request for the navigation. */
  fetchShell: (request: Request) => Promise<Response>;
  /** The cached offline page, or `undefined` when the cache was evicted. */
  readOfflinePage: () => Promise<Response | undefined>;
}

/**
 * Answer a navigation: the network when it answers, the offline page when it
 * does not.
 *
 * This is the whole of #546's promise — an uncached deep link while offline gets
 * a page that names what still works, not the browser's error page — so it is a
 * function with its own tests rather than a closure inside the worker.
 */
export async function respondToNavigation(
  request: Request,
  fallback: NavigationFallback,
): Promise<Response> {
  try {
    return await fallback.fetchShell(request);
  } catch {
    const cached = await fallback.readOfflinePage();
    if (cached) {
      return cached;
    }
    // The cache was evicted between install and this navigation. Say so plainly
    // rather than returning an opaque failure.
    return new Response("Offline", { status: 503, statusText: "Offline" });
  }
}

