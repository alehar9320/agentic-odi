import type { CanvasData } from "../types";

const REASON_TEXT: Record<string, string> = {
  mcp_unreachable: "the MCP server could not be reached",
  mcp_unreadable: "the MCP server returned nothing usable",
  demo: "demonstration data",
};

export interface CanvasStatus {
  label: "DEMO" | "OFFLINE";
  detail: string;
}

/**
 * True when the canvas is the seed prototype rather than the user's own work.
 * Falls back to `source` so a canvas cached by an older build is still labelled.
 */
export function isSimulatedCanvas(data: CanvasData | null | undefined): boolean {
  if (!data) {
    return false;
  }
  return data.provenance ? data.provenance.kind === "seed" : data.source === "seed";
}

/** The chip the rail shows, or `null` when the canvas is genuinely the user's. */
export function canvasStatus(data: CanvasData | null | undefined): CanvasStatus | null {
  if (!isSimulatedCanvas(data)) {
    return null;
  }
  const reason = data?.provenance?.reason ?? "demo";
  const detail = REASON_TEXT[reason] ?? reason.replaceAll("_", " ");
  const label = reason.startsWith("mcp_") ? "OFFLINE" : "DEMO";
  return { label, detail: `sample data — ${detail}` };
}

/** Whether a canvas holds anything worth drawing, so a board is not drawn over nothing. */
export function canvasHasRecords(data: CanvasData | null | undefined): boolean {
  if (!data) {
    return false;
  }
  return data.jobs.length > 0 || data.steps.length > 0 || data.outcomes.length > 0;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** When the saved copy was produced, from the one timestamp the cache carries. */
export function savedAtTime(data: CanvasData | null | undefined): number | null {
  const iso = data?.provenance?.generated_at;
  if (!iso) {
    return null;
  }
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * The caption for a board drawn from the saved copy. It names when the copy was
 * saved when the cache carries a timestamp, and claims no time it does not have.
 * `now` is injectable so the wording is testable without a clock.
 */
export function savedCopyCaption(
  data: CanvasData | null | undefined,
  now: number = Date.now(),
): string {
  const at = savedAtTime(data);
  if (at === null) {
    return "Saved copy on this device";
  }
  const elapsed = Math.max(0, now - at);
  if (elapsed < MINUTE) {
    return "Saved just now";
  }
  if (elapsed < HOUR) {
    const minutes = Math.round(elapsed / MINUTE);
    return `Saved ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }
  if (elapsed < DAY) {
    const hours = Math.round(elapsed / HOUR);
    return `Saved ${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.round(elapsed / DAY);
  return `Saved ${days} day${days === 1 ? "" : "s"} ago`;
}

/**
 * True when this board is the browser's own store and nobody else is keeping a
 * copy. `source` is the storage signal: `provenance.kind` says live or seeded,
 * which is about whether the work is the user's, not about where it lives — a
 * sidecar board and an IndexedDB board both read `live`.
 */
export function isBrowserCanvas(data: CanvasData | null | undefined): boolean {
  return data?.source === "local";
}

/** The one clause that names the store, so no receipt invents its own. */
export const LOCAL_BOARD_NOTE = "Saved in this browser.";
