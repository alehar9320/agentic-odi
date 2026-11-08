import { useSyncExternalStore } from "react";

import { SERVICE_WORKER_URL } from "./swRouting";

/**
 * The update handshake between the page and the service worker.
 *
 * The worker never calls `skipWaiting` on its own, so a new build waits until the
 * page says the moment is safe. This module is the page side of that deal: it
 * notices a waiting worker, tells the app so it can offer a reload, and takes the
 * waiting worker only when the person asks.
 *
 * The rules are plain functions over a narrow interface, so a unit test can drive
 * the whole handshake without a service-worker global.
 */

/** The subset of `ServiceWorker` the handshake uses. */
export interface WorkerLike {
  state: string;
  addEventListener(type: "statechange", listener: () => void): void;
  postMessage(message: unknown): void;
}

/** The subset of `ServiceWorkerRegistration` the handshake uses. */
export interface RegistrationLike {
  waiting: WorkerLike | null;
  installing: WorkerLike | null;
  addEventListener(type: "updatefound", listener: () => void): void;
  removeEventListener(type: "updatefound", listener: () => void): void;
}

/** The subset of `ServiceWorkerContainer` the handshake uses. */
export interface ContainerLike {
  controller: unknown;
  addEventListener(type: "controllerchange", listener: () => void): void;
  register(scriptURL: string): Promise<RegistrationLike>;
}

/**
 * Whether a waiting worker is an update for this page.
 *
 * A page with no controller is a first install: the new worker activates at once
 * and there is nothing to offer. A controlled page with a waiting worker has a
 * new build staged, which is the one case worth a reload.
 */
export function isUpdateWaiting(registration: RegistrationLike, controlled: boolean): boolean {
  return controlled && registration.waiting !== null;
}

export interface UpdateWatch {
  registration: RegistrationLike;
  /**
   * Whether this page is already controlled by a worker, read live.
   *
   * Read at report time, not capture time: a first load registers the worker and
   * becomes controlled only after it activates, so a value captured when the
   * watch is attached can be stale by the time a build is staged.
   */
  isControlled: () => boolean;
  /** Called once when a new build is waiting. */
  onUpdateReady: () => void;
}

/**
 * Watch a registration for a new build.
 *
 * Fires `onUpdateReady` at most once: either a worker is already waiting when the
 * app starts (a reload that did not take), or one appears after `updatefound`.
 * Returns a disposer for tests and unmount.
 */
export function watchForUpdates({
  registration,
  isControlled,
  onUpdateReady,
}: UpdateWatch): () => void {
  let fired = false;
  const report = () => {
    if (!fired && isUpdateWaiting(registration, isControlled())) {
      fired = true;
      onUpdateReady();
    }
  };

  // Follow an installing worker to `installed`, when it is waiting but not yet
  // controlling. The listener is attached defensively: the worker may already be
  // installed by the time we get here.
  const track = (installing: WorkerLike | null) => {
    if (!installing) {
      return;
    }
    const onStateChange = () => {
      if (installing.state === "installed") {
        report();
      }
    };
    installing.addEventListener("statechange", onStateChange);
    onStateChange();
  };

  const onUpdateFound = () => track(registration.installing);

  registration.addEventListener("updatefound", onUpdateFound);
  // An install already under way when the watch attached: its `updatefound` may
  // have fired before the listener existed, so follow it directly.
  track(registration.installing);
  // A worker already waiting when this page loaded: the reload did not take, so
  // the offer is still live.
  report();

  return () => registration.removeEventListener("updatefound", onUpdateFound);
}

/**
 * Take a waiting worker and reload once it controls the page.
 *
 * `skipWaiting` is only ever asked for here, from a person's click. The reload
 * waits for `controllerchange` so the new worker — and its new cache — serves the
 * next document, rather than reloading into the old one. It reloads at most once,
 * so the update can never loop.
 */
export function activateWaiting(
  registration: RegistrationLike,
  container: { addEventListener(type: "controllerchange", listener: () => void): void },
  reload: () => void,
): boolean {
  const waiting = registration.waiting;
  if (!waiting) {
    return false;
  }
  let reloaded = false;
  container.addEventListener("controllerchange", () => {
    if (reloaded) {
      return;
    }
    reloaded = true;
    reload();
  });
  waiting.postMessage({ type: "SKIP_WAITING" });
  return true;
}

/** What the shell reads to decide whether to offer a reload. */
export interface AppUpdateState {
  /** A new build is staged and waiting. */
  ready: boolean;
  /** The person hid the offer; it stays hidden for this page. */
  dismissed: boolean;
}

const EMPTY: AppUpdateState = { ready: false, dismissed: false };

let state: AppUpdateState = EMPTY;
let registration: RegistrationLike | null = null;
let container: ContainerLike | null = null;
const listeners = new Set<() => void>();

function setState(next: Partial<AppUpdateState>): void {
  const merged = { ...state, ...next };
  if (merged.ready === state.ready && merged.dismissed === state.dismissed) {
    return;
  }
  state = merged;
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function getSnapshot(): AppUpdateState {
  return state;
}

/** Subscribe to the update offer. Defaults to nothing waiting. */
export function useAppUpdate(): AppUpdateState {
  return useSyncExternalStore(subscribe, getSnapshot, () => EMPTY);
}

/** Hide the reload offer for this page. */
export function dismissAppUpdate(): void {
  setState({ dismissed: true });
}

/**
 * Reload into the new build, once.
 *
 * The waiting worker is asked to take over; the reload waits for it to control
 * the page. With no waiting worker — a stale tab, a test — a plain reload is the
 * honest fallback, so the button is never dead. `reload` is injected so a test can
 * watch the handshake without navigating.
 */
export function reloadForUpdate(reload: () => void = () => window.location.reload()): void {
  if (
    registration &&
    activateWaiting(registration, container ?? window.navigator.serviceWorker, reload)
  ) {
    return;
  }
  reload();
}

/** Reset module state. Tests only. */
export function resetAppUpdateForTests(): void {
  state = EMPTY;
  registration = null;
  container = null;
  listeners.clear();
}

/**
 * Register the worker and watch for the next build.
 *
 * Production only: in dev the worker would cache Vite's module responses and
 * serve stale code, and a failure to register must never break the app. Returns
 * the disposer so a test can stop the watch.
 */
export function initServiceWorker(
  serviceWorker: ContainerLike | undefined = typeof navigator === "undefined"
    ? undefined
    : (navigator.serviceWorker as ContainerLike | undefined),
  onReady: () => void = () => setState({ ready: true }),
): () => void {
  if (!serviceWorker) {
    return () => {};
  }
  container = serviceWorker;
  let dispose: () => void = () => {};
  void serviceWorker
    .register(SERVICE_WORKER_URL)
    .then((registered) => {
      registration = registered;
      dispose = watchForUpdates({
        registration: registered,
        isControlled: () => Boolean(serviceWorker.controller),
        onUpdateReady: onReady,
      });
    })
    .catch(() => {
      // An unregistered worker costs the offline shell, not the app.
    });
  return () => dispose();
}
