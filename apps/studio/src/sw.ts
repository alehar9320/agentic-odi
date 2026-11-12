import {
  CACHE_PREFIX,
  OFFLINE_URL,
  SHELL_URL,
  cacheName,
  respondToApi,
  respondToAsset,
  respondToNavigation,
  routeRequest,
} from "./lib/swRouting";

/**
 * The Studio's service worker.
 *
 * It does three things (#545):
 *
 * 1. **Precaches the built shell** — `index.html`, the hashed JS and CSS, the
 *    icons, the manifest, and `/offline.html` — so the installed app opens with
 *    no network and renders from cache.
 * 2. **Never caches the API.** `/api/**` goes to the network and nothing else: a
 *    cached canvas response would defeat the BFF's fallback and the conflict
 *    rules, and an offline call must fail fast rather than hang.
 * 3. **Updates without a trap.** A new build gets a new cache name, so `activate`
 *    retires the old one; the waiting worker is left alone until the app asks for
 *    it, so an update never swaps code mid-sentence.
 *
 * `skipWaiting` is never called here. The page decides when to take a waiting
 * worker (`swUpdate.ts`), because only it knows whether a turn is streaming.
 */

/**
 * The service-worker globals this file uses.
 *
 * The app compiles against the DOM lib, which has no `ServiceWorkerGlobalScope`
 * (that lives in the WebWorker lib, whose declarations collide with DOM). Naming
 * only the members used keeps one tsconfig for the whole app.
 */
interface ExtendableEventLike {
  waitUntil(promise: Promise<unknown>): void;
}

interface FetchEventLike extends ExtendableEventLike {
  request: Request;
  respondWith(response: Response | Promise<Response>): void;
}

interface MessageEventLike {
  data: unknown;
}

interface ServiceWorkerScope {
  location: Location;
  clients: { claim(): Promise<void> };
  skipWaiting(): Promise<void>;
  addEventListener(
    type: "install" | "activate",
    listener: (event: ExtendableEventLike) => void,
  ): void;
  addEventListener(type: "fetch", listener: (event: FetchEventLike) => void): void;
  addEventListener(type: "message", listener: (event: MessageEventLike) => void): void;
}

const worker = self as unknown as ServiceWorkerScope;

// A new build gets a new cache name, so `activate` retires the previous one
// instead of leaving it behind. One cache name, deleted old ones.
const CACHE_NAME = cacheName(__STUDIO_CACHE_VERSION__);

// The shell files the app build emitted, as origin-root URLs.
const PRECACHE = __STUDIO_PRECACHE__;

// The shell is answered for a navigation the network could not. `index.html` is
// always in the list; the set is used to decide cache-first assets.
const PRECACHE_SET = new Set(PRECACHE);

worker.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      // One file at a time, tolerating a failure: `addAll` rejects as a unit, so
      // a single 404 would abort the install and leave the app with no worker at
      // all — and no offline page either. Best-effort still caches the shell.
      await Promise.all(
        PRECACHE.map((url) =>
          cache.add(new Request(url, { cache: "reload" })).catch(() => undefined),
        ),
      );
    })(),
  );
});

worker.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      );
      await worker.clients.claim();
    })(),
  );
});

worker.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const route = routeRequest(url, request, { origin: worker.location.origin, precache: PRECACHE_SET });

  // Anything the worker does not own is left to the browser. The API is never
  // intercepted at all, so no cache can ever answer it.
  if (route === "other") {
    return;
  }

  event.respondWith(
    (async () => {
      switch (route) {
        case "api":
          return respondToApi(request, { fetchNetwork: (req) => fetch(req) });
        case "asset":
          return respondToAsset(request, {
            // `ignoreVary`: the app server stamps `Vary: Origin` on static
            // assets (its CORS middleware), and a module import does not always
            // carry the Origin the precache stored. The shell is same-origin and
            // content-hashed, so Vary must not decide whether it can load.
            readCache: () => caches.match(request, { ignoreVary: true }),
            fetchNetwork: (req) => fetch(req),
          });
        default:
          return respondToNavigation(request, {
            fetchShell: (req) => fetch(req),
            readShell: () => caches.match(SHELL_URL, { ignoreVary: true }),
            readOfflinePage: () => caches.match(OFFLINE_URL, { ignoreVary: true }),
          });
      }
    })(),
  );
});

// The page asks the waiting worker to take over once it is safe to reload. Only
// this message calls `skipWaiting`, so an update never swaps code on its own.
worker.addEventListener("message", (event) => {
  const data = event.data as { type?: string } | null;
  if (data?.type === "SKIP_WAITING") {
    void worker.skipWaiting();
  }
});
