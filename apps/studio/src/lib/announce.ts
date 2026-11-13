/**
 * One polite live region for the whole app. Every write receipt, and anything
 * else that needs to say a thing happened, routes through here so a burst of
 * writes is a sentence each rather than one per render — a second region would
 * let two announcements race and read in the wrong order.
 */

let region: HTMLElement | null = null;

function ensureRegion(): HTMLElement | null {
  if (typeof document === "undefined") {
    return null;
  }
  if (region && region.isConnected) {
    return region;
  }
  const existing = document.getElementById("studio-announcer");
  if (existing) {
    region = existing;
    return region;
  }
  const created = document.createElement("div");
  created.id = "studio-announcer";
  created.className = "sr-only";
  created.setAttribute("aria-live", "polite");
  created.setAttribute("aria-atomic", "true");
  document.body.appendChild(created);
  region = created;
  return region;
}

/**
 * Announce one sentence. An empty message is a no-op, so a caller can pass the
 * result of `receiptAnnouncement` without guarding it.
 */
export function announce(message: string | null | undefined): void {
  if (!message) {
    return;
  }
  const node = ensureRegion();
  if (!node) {
    return;
  }
  // Clear first: a live region only re-reads text that actually changed, so the
  // same sentence twice in a row needs the empty pass between them.
  node.textContent = "";
  node.textContent = message;
}

/** Test seam: forget the cached region so a fresh document starts clean. */
export function resetAnnouncer(): void {
  region = null;
}
