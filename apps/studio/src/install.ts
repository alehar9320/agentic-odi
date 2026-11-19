const DISMISSED_KEY = "studio.install.dismissed";

let deferredPrompt: Event | null = null;

/** The display modes that mean the page is running as its own window. */
const INSTALLED_DISPLAY_MODES = ["standalone", "minimal-ui", "fullscreen"] as const;

/**
 * True when the app is already running as an installed PWA.
 *
 * This answers "is it installed?", so it must not be coupled to whether an
 * install prompt is pending: a browser that can still offer to install reports
 * "not installed" even in standalone mode otherwise. The display-mode queries
 * cover a desktop install; `navigator.standalone` covers iOS Safari.
 */
export function isInstalled(): boolean {
  try {
    const byDisplayMode =
      typeof window.matchMedia === "function" &&
      INSTALLED_DISPLAY_MODES.some((mode) => window.matchMedia(`(display-mode: ${mode})`).matches);
    const byNavigator =
      (window.navigator as unknown as { standalone?: boolean }).standalone === true;
    return byDisplayMode || byNavigator;
  } catch {
    return false;
  }
}

/** True when the person has dismissed the install prompt. */
export function isDismissed(): boolean {
  try {
    return typeof window.localStorage !== "undefined" && window.localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Mark the install prompt as dismissed so it is not offered again. */
export function dismissInstall(): void {
  try {
    if (typeof window.localStorage !== "undefined") {
      window.localStorage.setItem(DISMISSED_KEY, "1");
    }
  } catch {
    // Storage unavailable; dismissal is not persisted.
  }
}

/** Offer the install prompt. Returns false when there is nothing to offer. */
export function offerInstall(): boolean {
  if (!deferredPrompt || isInstalled() || isDismissed()) {
    return false;
  }
  const promptEvent = deferredPrompt as unknown as { prompt?: () => Promise<void> };
  void promptEvent.prompt?.();
  deferredPrompt = null;
  return true;
}

/** Capture the deferred install prompt when the browser fires it. */
function onBeforeInstallPrompt(event: Event): void {
  event.preventDefault();
  deferredPrompt = event;
}

/** Wire the install prompt listener. Safe to call multiple times. */
export function initInstall(): void {
  if (typeof window === "undefined" || isInstalled() || isDismissed()) {
    return;
  }
  window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
}
