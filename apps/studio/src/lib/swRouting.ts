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

/** The precached shell document. It answers a navigation the network could not. */
export const SHELL_URL = "/index.html";

/** The prefix of every shell cache. One cache name per build, retired on activate. */
export const CACHE_PREFIX = "studio-shell-";

/** How long a navigation waits for the network before the cached shell answers. */
export const NAVIGATION_TIMEOUT_MS = 3_000;

/** The cache name for a build. The version moves with the release, so `activate`
 * can delete every other `studio-shell-*` cache without guessing. */
export function cacheName(build: string): string {
  return `${CACHE_PREFIX}${build}`;
}

/** The strategy the worker applies to a request. */
export type Route =
  /** The API: network-only, never read from or written to a cache. */
  | "api"
  /** A top-level navigation: network-first, then the cached shell, then offline. */
  | "navigation"
  /** A precached, content-hashed asset: cache-first. */
  | "asset"
  /** Anything else: the worker leaves it alone. */
  | "other";

/**
 * The API is never intercepted, cached, or served from cache.
 *
 * A cached canvas response would defeat the browser BFF's fallback and the
 * conflict rules, so `/api/` requests take the network and nothing else.
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

/**
 * A precached file: an entry from the build's manifest, or a hashed `/assets/`
 * file. Hashed names change with their contents, so a hit is immutable and the
 * cache may answer without asking the network.
 */
export function isPrecached(
  url: URL,
  origin: string,
  precache: ReadonlySet<string> | undefined,
): boolean {
  if (url.origin !== origin) {
    return false;
  }
  if (precache?.has(url.pathname)) {
    return true;
  }
  // A hashed asset whose manifest entry is missing (a stale worker, a hand-run
  // build) is still immutable, so it is cache-first too.
  return url.pathname.startsWith("/assets/");
}

/**
 * Classify a request. This is the whole of the worker's policy, in one place, so
 * a test can assert each rule without a browser.
 */
export function routeRequest(
  url: URL,
  request: { method: string; mode: string },
  context: { origin: string; precache?: ReadonlySet<string> },
): Route {
  if (isApiRequest(url, context.origin)) {
    return "api";
  }
  if (isNavigationRequest(request)) {
    return "navigation";
  }
  if (request.method === "GET" && isPrecached(url, context.origin, context.precache)) {
    return "asset";
  }
  return "other";
}

/** The collaborators the API handler needs. Only the network is consulted. */
export interface ApiNetwork {
  /** The real network request. There is no cache on this path. */
  fetchNetwork: (request: Request) => Promise<Response>;
}

/**
 * Answer an API request from the network, and only the network.
 *
 * No cache read, no cache write, no fallback: a cached canvas response would
 * defeat the BFF's fallback and the conflict rules. When the network is gone the
 * fetch rejects at once, so the call fails fast instead of hanging on a cache
 * lookup that would only ever return something stale.
 */
export async function respondToApi(request: Request, network: ApiNetwork): Promise<Response> {
  return network.fetchNetwork(request);
}

/** The collaborators the asset handler needs. */
export interface AssetCache {
  /** The cached response, or `undefined` on a miss. */
  readCache: () => Promise<Response | undefined>;
  /** The real network request, used only on a miss. */
  fetchNetwork: (request: Request) => Promise<Response>;
}

/**
 * Answer a precached asset: the cache first, the network only on a miss.
 *
 * The names are content-hashed, so a cache hit is the correct bytes for this
 * build and the network is not asked at all.
 */
export async function respondToAsset(request: Request, cache: AssetCache): Promise<Response> {
  const cached = await cache.readCache();
  if (cached) {
    return cached;
  }
  return cache.fetchNetwork(request);
}

/** The collaborators the navigation handler needs, injected so a test can drive
 * the offline path without a service-worker global. */
export interface NavigationFallback {
  /** The real network request for the navigation. */
  fetchShell: (request: Request) => Promise<Response>;
  /** The cached shell document, or `undefined` when the cache was evicted. */
  readShell: () => Promise<Response | undefined>;
  /** The cached offline page, or `undefined` when the cache was evicted. */
  readOfflinePage: () => Promise<Response | undefined>;
  /** How long the network may take before the cache answers. */
  timeoutMs?: number;
}

/** Resolve with `promise`, or reject once `ms` have passed. */
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("navigation timed out")), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

/**
 * Answer a navigation: the network when it answers in time, the precached shell
 * when it does not, and the offline page only when the shell itself is gone.
 *
 * The shell is what makes the installed app open with no network: the cached
 * document boots the app, which reads its canvas from IndexedDB. The offline page
 * is the last resort for a cold miss whose shell cache was evicted.
 */
export async function respondToNavigation(
  request: Request,
  fallback: NavigationFallback,
): Promise<Response> {
  try {
    return await withTimeout(
      fallback.fetchShell(request),
      fallback.timeoutMs ?? NAVIGATION_TIMEOUT_MS,
    );
  } catch {
    const shell = await fallback.readShell();
    if (shell) {
      return shell;
    }
    const offline = await fallback.readOfflinePage();
    if (offline) {
      return offline;
    }
    // Both the shell and the offline page were evicted between install and this
    // navigation. Say so plainly rather than returning an opaque failure.
    return new Response("Offline", { status: 503, statusText: "Offline" });
  }
}
