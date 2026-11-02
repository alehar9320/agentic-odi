/**
 * The install prompt, offered honestly.
 *
 * A browser only offers to install a site as an app when it can see a manifest
 * and decides the site qualifies. It signals that moment with a
 * `beforeinstallprompt` event, which can be captured and shown later — or not at
 * all. This module captures it, remembers a dismissal, and reports whether the
 * app is already running in an installed window, so the control that calls
 * `prompt()` appears only when it can do something.
 *
 * Nothing here registers a service worker, and nothing auto-prompts: the offer
 * is made when a person asks for it (issue #544).
 */

/** The Chromium-only event that carries the deferred install prompt. */
export interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

export type InstallOutcome = "accepted" | "dismissed" | "unavailable";

export interface InstallSnapshot {
  /** True only when the browser has offered a prompt, it is unused, and no dismissal is remembered. */
  canInstall: boolean;
  /** True when the document is already running as an installed app. */
  installed: boolean;
}

export interface InstallController {
  getSnapshot(): InstallSnapshot;
  subscribe(listener: () => void): () => void;
  /** Show the browser's prompt. Resolves with what the person chose. */
  prompt(): Promise<InstallOutcome>;
  /** Remember a dismissal so the offer is not made again. */
  dismiss(): void;
  /** Detach from the window. */
  dispose(): void;
}

export const INSTALL_DISMISSED_KEY = "studio.pwa.installDismissed";

type PreferenceStorage = Pick<Storage, "getItem" | "setItem">;

interface InstallControllerOptions {
  /** The window to listen on; defaults to the real one, and accepts null in tests. */
  targetWindow?: Window | null;
  /** Where the dismissal is remembered; null disables persistence. */
  storage?: PreferenceStorage | null;
}

function defaultWindow(): Window | null {
  return typeof window === "undefined" ? null : window;
}

function defaultStorage(): PreferenceStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function readDismissed(storage: PreferenceStorage | null): boolean {
  if (!storage) {
    return false;
  }
  try {
    return storage.getItem(INSTALL_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * True when the document is displayed as an installed app rather than a tab.
 * Chrome reports this through the `standalone` display mode; iOS Safari, which
 * has no `beforeinstallprompt`, reports it on `navigator.standalone`.
 */
export function isInstalled(targetWindow: Window | null): boolean {
  if (!targetWindow) {
    return false;
  }
  const displayMode =
    typeof targetWindow.matchMedia === "function" &&
    targetWindow.matchMedia("(display-mode: standalone)").matches;
  const iosStandalone =
    (targetWindow.navigator as { standalone?: boolean } | undefined)?.standalone === true;
  return displayMode || iosStandalone;
}

export function createInstallController(
  options: InstallControllerOptions = {},
): InstallController {
  const targetWindow = options.targetWindow === undefined ? defaultWindow() : options.targetWindow;
  const storage = options.storage === undefined ? defaultStorage() : options.storage;

  let deferred: InstallPromptEvent | null = null;
  let dismissed = readDismissed(storage);
  let installed = isInstalled(targetWindow);
  const listeners = new Set<() => void>();

  // One stable snapshot object per change: useSyncExternalStore compares by
  // reference, and a fresh object on every read would loop forever.
  let snapshot: InstallSnapshot = {
    canInstall: deferred !== null && !installed && !dismissed,
    installed,
  };

  function publish(): void {
    snapshot = { canInstall: deferred !== null && !installed && !dismissed, installed };
    for (const listener of listeners) {
      listener();
    }
  }

  function onBeforeInstallPrompt(event: Event): void {
    // Suppress the browser's own mini-infobar; the offer is ours to make, and
    // only when the person is ready for it.
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    publish();
  }

  function onAppInstalled(): void {
    deferred = null;
    installed = true;
    dismissed = false;
    publish();
  }

  function rememberDismissal(): void {
    dismissed = true;
    deferred = null;
    if (storage) {
      try {
        storage.setItem(INSTALL_DISMISSED_KEY, "1");
      } catch {
        // Storage is an optimisation; the offer stays hidden for this session.
      }
    }
  }

  targetWindow?.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  targetWindow?.addEventListener("appinstalled", onAppInstalled);

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    async prompt() {
      const event = deferred;
      if (!event) {
        return "unavailable";
      }
      // The event is single-use: clear it before awaiting so a second click
      // cannot replay a prompt the browser has already retired.
      deferred = null;
      publish();
      await event.prompt();
      const { outcome } = await event.userChoice;
      if (outcome === "accepted") {
        installed = true;
        publish();
        return "accepted";
      }
      rememberDismissal();
      publish();
      return "dismissed";
    },
    dismiss() {
      rememberDismissal();
      publish();
    },
    dispose() {
      targetWindow?.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      targetWindow?.removeEventListener("appinstalled", onAppInstalled);
      listeners.clear();
    },
  };
}
