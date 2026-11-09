const DISMISSED_KEY = "studio.install.dismissed";

let deferredPrompt: Event | null = null;

/** True when the app is already running as an installed PWA. */
export function isInstalled(): boolean {
  try {
    return (
      (typeof window.matchMedia === "function" &&
        window.matchMedia("(display-mode: standalone)").matches) ||
      (window.navigator as unknown as { standalone?: boolean }).standalone === true
    ) && !deferredPrompt;
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
