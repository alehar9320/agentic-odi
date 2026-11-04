import {
  OFFLINE_URL,
  isApiRequest,
  isNavigationRequest,
  respondToNavigation,
} from "./lib/swRouting";

/**
 * The Studio's service worker.
 *
 * Its job in this change (#546) is the navigation fallback: a deep link opened
 * while offline, whose shell was never cached, would otherwise land on the
 * browser's own error page. The failed navigation is answered with
 * `/offline.html`, a themed page that says the app is installed and names what
 * still works on the device.
 *
 * The app-shell precache and the cache-first rules for hashed assets are #545's
 * work, so this worker deliberately does not precache the shell — there is no
 * second shell implementation to keep in step.
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

interface ServiceWorkerScope {
  location: Location;
  clients: { claim(): Promise<void> };
  addEventListener(
    type: "install" | "activate",
    listener: (event: ExtendableEventLike) => void,
  ): void;
  addEventListener(type: "fetch", listener: (event: FetchEventLike) => void): void;
}

const worker = self as unknown as ServiceWorkerScope;

// A new build gets a new cache name, so `activate` retires the previous one
// instead of leaving it behind.
const CACHE_NAME = `studio-offline-${__STUDIO_BUILD_DATE__}`;

worker.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL)));
});

worker.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)),
      );
      await worker.clients.claim();
    })(),
  );
});

worker.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // The API is never intercepted. A cached canvas response would defeat the
  // browser BFF's fallback and the conflict rules, so `/api/` bypasses here.
  if (isApiRequest(url, worker.location.origin)) {
    return;
  }
  if (!isNavigationRequest(request)) {
    return;
  }

  event.respondWith(
    respondToNavigation(request, {
      fetchShell: (shellRequest) => fetch(shellRequest),
      readOfflinePage: () => caches.match(OFFLINE_URL),
    }),
  );
});
