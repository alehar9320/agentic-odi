import { useSyncExternalStore } from "react";

/**
 * Whether the browser believes it has a network connection.
 *
 * `navigator.onLine` is a coarse signal — it says a network interface is up,
 * not that the sidecar answers — so this drives the offline notice only. What
 * the sidecar can do is measured by its own probes.
 */
export function isOnline(): boolean {
  if (typeof navigator === "undefined" || typeof navigator.onLine !== "boolean") {
    return true;
  }
  return navigator.onLine;
}

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/**
 * Subscribe to the browser's connectivity state.
 *
 * Defaults to online when the API is missing, so a test environment or an
 * older browser never shows an offline notice it cannot verify.
 */
export function useOnlineStatus(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true);
}
